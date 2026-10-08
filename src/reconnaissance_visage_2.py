#!/usr/bin/env python3
"""Webcam Raspberry Pi : YuNet + SFace, affichage indépendant de l'analyse.
Installation : sudo apt install python3-opencv python3-numpy alsa-utils
Modèles : python3 reconnaissance_visage_2.py --setup
Enregistrer : python3 reconnaissance_visage_2.py --enroll Hichem --samples 30
Surveiller : python3 reconnaissance_visage_2.py
Lister / supprimer : --list / --delete Hichem
Mesurer la caméra depuis SSH sans bureau : --camera-test
Les anciens recadrages LBPH restent conservés, mais il faut réenregistrer
les personnes pour SFace. Données : ~/visages_connus ; modèles : ~/modeles_visages.
MJPEG 640x480 à 30 FPS demandé par défaut, sans garantie matérielle.
Q ou Échap ferme la fenêtre. Lancer la fenêtre depuis le bureau du Pi.
"""
import argparse
from collections import deque
import hashlib
import math
import os
from pathlib import Path
import queue
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import unicodedata
import urllib.request
import wave

MODELS = {
    'face_detection_yunet_2023mar.onnx': '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4',
    'face_recognition_sface_2021dec.onnx': '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79',
}
FORMAT = 'sface-2021dec-v1'


def valid_person_name(name):
    name = name.strip()
    if not re.fullmatch(r'[\w][\w -]{0,39}', name, re.UNICODE):
        raise ValueError('Prénom invalide : lettres/chiffres, espaces, tirets ou underscores.')
    return name


def person_path(root, name):
    root = root.expanduser().resolve()
    target = root / valid_person_name(name)
    if target.is_symlink():
        raise ValueError('Le dossier de cette personne est un lien symbolique : opération refusée.')
    return target


def delete_person(root, name):
    target = person_path(root, name)
    if not target.exists():
        print('Personne absente :', name)
        return False
    if not target.is_dir():
        raise ValueError('Ce chemin ne correspond pas à un dossier de personne.')
    shutil.rmtree(target)
    print('Tous les exemples de', name, 'ont été supprimés. Redémarre la surveillance en cours.')
    return True


def list_people(root):
    if not root.exists():
        print('Aucune personne enregistrée.')
        return
    for folder in sorted(root.iterdir()):
        if folder.is_dir() and not folder.is_symlink():
            print(folder.name, ':', len(list(folder.glob('*.npz'))),
                  'session(s) SFace ;', len(list(folder.glob('*.png'))), 'ancien(s) exemple(s) LBPH')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def setup_models(root):
    root.mkdir(parents=True, exist_ok=True)
    for filename, expected in MODELS.items():
        destination = root / filename
        if destination.is_file() and digest(destination) == expected:
            print('Modèle déjà prêt :', filename)
            continue
        family = 'face_detection_yunet' if 'yunet' in filename else 'face_recognition_sface'
        relative = f'models/{family}/{filename}'
        urls = [f'https://huggingface.co/opencv/opencv_zoo/resolve/main/{relative}',
                f'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/{relative}']
        failures = []
        for url in urls:
            fd, temporary = tempfile.mkstemp(dir=root, suffix='.download')
            os.close(fd)
            temporary = Path(temporary)
            try:
                print('Téléchargement :', filename, flush=True)
                request = urllib.request.Request(url, headers={'User-Agent': 'vision-pi/2'})
                with urllib.request.urlopen(request, timeout=45) as source, temporary.open('wb') as output:
                    shutil.copyfileobj(source, output)
                if digest(temporary) != expected:
                    raise RuntimeError('Empreinte du modèle incorrecte.')
                os.replace(temporary, destination)
                break
            except Exception as exc:
                failures.append(str(exc))
            finally:
                temporary.unlink(missing_ok=True)
        else:
            raise RuntimeError('Téléchargement impossible : ' + ' ; '.join(failures))
    print('Modèles prêts. La reconnaissance fonctionne ensuite sans Internet.')


def normalized(np, vector):
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if vector.size != 128 or not np.isfinite(vector).all() or norm < 1e-8:
        raise ValueError('Empreinte SFace invalide.')
    return vector / norm


class Gallery:
    def __init__(self, np, root, threshold, margin):
        self.np, self.threshold, self.margin = np, threshold, margin
        self.people = {}
        if not root.exists():
            return
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or folder.is_symlink():
                continue
            vectors = []
            for path in sorted(folder.glob('*.npz')):
                try:
                    with np.load(path, allow_pickle=False) as data:
                        if str(data['format'].item()) != FORMAT:
                            raise ValueError('format incompatible')
                        vectors.extend(normalized(np, v) for v in data['embeddings'])
                except (OSError, ValueError, KeyError) as exc:
                    print('Session ignorée :', path.name, exc)
            if vectors:
                self.people[folder.name] = np.stack(vectors)
                print(folder.name, ':', len(vectors), 'exemples SFace')
            elif list(folder.glob('*.png')):
                print(folder.name, ': anciens exemples LBPH ; réenregistrer avec --enroll.')

    def identify(self, vector):
        ranking = []
        for name, references in self.people.items():
            scores = references @ vector
            # Deux bons exemples donnent un résultat plus robuste qu'un seul.
            count = min(2, len(scores))
            score = float(self.np.sort(scores)[-count:].mean())
            ranking.append((score, name))
        ranking.sort(reverse=True)
        if not ranking:
            return None, 0.0
        score, name = ranking[0]
        ambiguous = len(ranking) > 1 and score - ranking[1][0] < self.margin
        return (name if score >= self.threshold and not ambiguous else None), score


class Engine:
    def __init__(self, cv, np, models, analysis_width):
        self.cv, self.np, self.width = cv, np, analysis_width
        for filename, expected in MODELS.items():
            path = models / filename
            if not path.is_file() or digest(path) != expected:
                raise RuntimeError('Modèle absent/invalide. Lance d’abord --setup.')
        self.detector = cv.FaceDetectorYN.create(str(models / next(iter(MODELS))), '', (320, 320), .8, .3, 500)
        self.recognizer = cv.FaceRecognizerSF.create(str(models / list(MODELS)[1]), '')

    def detect(self, frame):
        height, width = frame.shape[:2]
        scale = min(1.0, self.width / width)
        small = self.cv.resize(frame, (int(width * scale), int(height * scale)))
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.detector.detect(small)
        if faces is None:
            return []
        # Remapper boîte ET repères vers la capture pour aligner un visage net.
        faces = faces.copy()
        faces[:, [0, 2, 4, 6, 8, 10, 12]] *= width / small.shape[1]
        faces[:, [1, 3, 5, 7, 9, 11, 13]] *= height / small.shape[0]
        return list(faces)

    def extract(self, frame, face):
        crop = self.recognizer.alignCrop(frame, face)
        vector = normalized(self.np, self.recognizer.feature(crop))
        return crop, vector


def overlap(a, b):
    x, y, w, h = a[:4]
    u, v, s, t = b[:4]
    intersection = max(0, min(x+w, u+s)-max(x, u)) * max(0, min(y+h, v+t)-max(y, v))
    return intersection / max(1, w*h+s*t-intersection)


class Worker:
    def __init__(self, engine, gallery, enroll=False):
        self.engine, self.gallery, self.enroll = engine, gallery, enroll
        self.queue = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.result = None
        self.error = None
        self.stop = threading.Event()
        self.previous = []
        self.last_sequence = -1
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def submit(self, item):
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            pass  # Une seule analyse en attente, jamais un historique vidéo.

    def run(self):
        while not self.stop.is_set():
            try:
                seq, captured, frame = self.queue.get(timeout=.2)
            except queue.Empty:
                continue
            if seq == self.last_sequence:
                continue
            self.last_sequence = seq
            try:
                start = time.monotonic()
                faces = self.engine.detect(frame)
                records, tracks = [], []
                used = set()
                for face in faces:
                    crop, vector = self.engine.extract(frame, face)
                    name, score = self.gallery.identify(vector)
                    candidates = [(overlap(face, old[0]), index, old) for index, old in enumerate(self.previous)
                                  if index not in used and captured-old[3] < 3]
                    best = max(candidates, default=(0, -1, None), key=lambda item: item[0])
                    streak = 1
                    if best[0] > .3:
                        used.add(best[1])
                        if best[2][1] == name:
                            streak = best[2][2] + 1
                    label = name if name is not None and streak >= 2 else None
                    state = 'known' if label else ('checking' if name else 'unknown')
                    tracks.append((face.copy(), name, streak, captured))
                    records.append((face, label, score, state, crop if self.enroll else None,
                                    vector if self.enroll else None))
                self.previous = tracks
                with self.lock:
                    self.result = (seq, captured, records, time.monotonic()-start)
            except Exception as exc:
                with self.lock:
                    self.error = str(exc)
                return

    def snapshot(self):
        with self.lock:
            return self.result, self.error

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


class Camera:
    def __init__(self, capture):
        self.capture, self.lock = capture, threading.Lock()
        self.latest, self.error = None, None
        self.times = deque(maxlen=90)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        seq = 0
        try:
            while not self.stop.is_set():
                ok, frame = self.capture.read()
                if not ok or frame is None:
                    raise RuntimeError('Lecture caméra impossible. Ferme VLC et vérifie le câble USB.')
                now = time.monotonic()
                with self.lock:
                    self.latest = (seq, now, frame)
                    self.times.append(now)
                seq += 1
        except Exception as exc:
            with self.lock:
                self.error = str(exc)
        finally:
            self.capture.release()

    def snapshot(self):
        with self.lock:
            fps = ((len(self.times)-1)/(self.times[-1]-self.times[0])
                   if len(self.times) > 1 and self.times[-1] > self.times[0] else 0)
            return self.latest, self.error, fps

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


class AlertGate:
    def __init__(self, cooldown=30, absence=3):
        self.cooldown, self.absence = cooldown, absence
        self.last_alert, self.last_seen = float('-inf'), None
        self.alerted, self.streak = False, 0

    def update(self, present, now):
        if self.last_seen is not None and now-self.last_seen >= self.absence:
            self.alerted, self.streak = False, 0
        if not present:
            self.streak = 0
            return False
        self.last_seen = now
        self.streak += 1
        if self.streak >= 3 and not self.alerted and now-self.last_alert >= self.cooldown:
            self.alerted, self.last_alert = True, now
            return True
        return False


def make_beep(path):
    rate = 16000
    frames = []
    for i in range(rate):
        phase = (i/rate) % .5
        amplitude = 7000 if phase < .25 else 0
        frames.append(struct.pack('<h', int(amplitude * math.sin(2*math.pi*880*i/rate))))
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        output.writeframes(b''.join(frames))


def play_beep(path):
    for player in ('paplay', 'aplay'):
        executable = shutil.which(player)
        if executable:
            try:
                if subprocess.run([executable, str(path)], timeout=4,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                    return
            except (OSError, subprocess.TimeoutExpired):
                pass
    print('Bip indisponible : vérifie la sortie audio du Pi.', flush=True)


def open_camera(cv, args):
    source = int(args.camera) if args.camera.isdigit() else args.camera
    capture = cv.VideoCapture(source, cv.CAP_V4L2)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError('Caméra indisponible. Ferme VLC et vérifie --camera /dev/video0.')
    capture.set(cv.CAP_PROP_FOURCC, cv.VideoWriter_fourcc(*('YUYV' if args.raw else 'MJPG')))
    capture.set(cv.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv.CAP_PROP_FRAME_HEIGHT, args.height or round(args.width*3/4))
    capture.set(cv.CAP_PROP_FPS, args.fps)
    capture.set(cv.CAP_PROP_BUFFERSIZE, 1)
    code = int(capture.get(cv.CAP_PROP_FOURCC))
    codec = ''.join(chr((code >> (8*i)) & 255) for i in range(4))
    print('Mode annoncé :', int(capture.get(cv.CAP_PROP_FRAME_WIDTH)), 'x',
          int(capture.get(cv.CAP_PROP_FRAME_HEIGHT)), codec,
          capture.get(cv.CAP_PROP_FPS), 'FPS ; mesure réelle dans la fenêtre.', flush=True)
    return Camera(capture)


def save_session(np, folder, vectors):
    folder.mkdir(parents=True, exist_ok=True)
    filename = folder / f'sface_{time.time_ns()}.npz'
    fd, temporary = tempfile.mkstemp(dir=folder, suffix='.npz')
    try:
        with os.fdopen(fd, 'wb') as output:
            np.savez_compressed(output, format=FORMAT, embeddings=np.stack(vectors))
        os.replace(temporary, filename)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return filename


def run_gui(cv, np, args, camera, worker):
    gate = AlertGate()
    result_seq, shown_seq = -1, -1
    last_submit, red_until, last_sample = 0, 0, 0
    submitted_seq = -1
    opened = time.monotonic()
    vectors, displayed = [], deque(maxlen=90)
    folder = person_path(args.data, args.enroll) if args.enroll else None
    window = 'Camera - reconnaissance (Q pour quitter)'
    cv.namedWindow(window, cv.WINDOW_NORMAL)
    message = 'Bouge lentement : face, legerement gauche/droite, distances variees'
    with tempfile.TemporaryDirectory(prefix='alerte-visage-') as temp:
        beep = Path(temp) / 'alerte.wav'
        make_beep(beep)
        try:
            while True:
                now = time.monotonic()
                latest, error, fps = camera.snapshot()
                result, worker_error = worker.snapshot()
                if error or worker_error:
                    raise RuntimeError(error or worker_error)
                if latest is None and now-opened > 10:
                    raise RuntimeError('Aucune image caméra reçue après 10 secondes.')
                if latest is not None:
                    seq, captured, frame = latest
                    if seq != submitted_seq and now-last_submit >= 1/args.detect_fps:
                        worker.submit(latest)
                        submitted_seq = seq
                        last_submit = now
                    if result is not None and result[0] != result_seq:
                        result_seq = result[0]
                        if now-result[1] <= args.max_age:
                            records = result[2]
                            if args.enroll:
                                message = 'Un seul visage, assez grand et bien eclaire'
                                if len(records) == 1 and now-last_sample >= .7:
                                    face, _, _, _, crop, vector = records[0]
                                    gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)
                                    sharpness = cv.Laplacian(gray, cv.CV_64F).var()
                                    brightness = float(gray.mean())
                                    duplicate = any(float(vector @ old) > .995 for old in vectors)
                                    if min(face[2:4]) < 80:
                                        message = 'Approche un peu le visage'
                                    elif sharpness < args.min_sharpness or not 25 < brightness < 230:
                                        message = 'Image floue/sombre : plus de lumiere, bouge moins vite'
                                    elif duplicate:
                                        message = 'Change legerement l angle ou la distance'
                                    else:
                                        vectors.append(vector.copy())
                                        last_sample = now
                                        message = 'Exemple ajoute : varie doucement angle/distance'
                                        print('Exemple', len(vectors), '/', args.samples, flush=True)
                                if len(vectors) >= args.samples:
                                    break
                            elif gate.update(any(r[3] == 'unknown' for r in records), now):
                                red_until = now+5
                                print('ALERTE : visage inconnu', flush=True)
                                threading.Thread(target=play_beep, args=(beep,), daemon=True).start()
                    if seq != shown_seq:
                        shown_seq = seq
                        scale = min(1., args.preview_width/frame.shape[1])
                        view = cv.resize(frame, (int(frame.shape[1]*scale), int(frame.shape[0]*scale)))
                        if result and now-result[1] <= args.max_age:
                            for face, name, score, state, _, _ in result[2]:
                                x, y, w, h = [int(v*scale) for v in face[:4]]
                                color = (0, 220, 0) if state == 'known' else (0, 180, 255)
                                cv.rectangle(view, (x, y), (x+w, y+h), color, 2)
                                label = name or ('Verification...' if state == 'checking' else 'Inconnu')
                                label = unicodedata.normalize('NFKD', label).encode('ascii', 'ignore').decode()
                                if args.scores:
                                    label += f' {score:.2f}'
                                cv.putText(view, label, (max(0,x), max(18,y-7)), cv.FONT_HERSHEY_SIMPLEX, .55, color, 2)
                        displayed.append(now)
                        render_fps = (len(displayed)-1)/(displayed[-1]-displayed[0]) if len(displayed)>1 else 0
                        latency = result[3]*1000 if result else 0
                        cv.putText(view, f'Camera {fps:.1f} FPS | affichage {render_fps:.1f} | analyse {latency:.0f} ms',
                                   (8, 22), cv.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
                        if args.enroll:
                            cv.putText(view, f'{len(vectors)}/{args.samples} - {message}', (8,view.shape[0]-15),
                                       cv.FONT_HERSHEY_SIMPLEX, .4, (0,255,255), 1)
                        elif now < red_until:
                            cv.rectangle(view, (0,0), (view.shape[1]-1, view.shape[0]-1), (0,0,255), 8)
                            cv.putText(view, 'ALERTE : VISAGE INCONNU', (10,50), cv.FONT_HERSHEY_SIMPLEX, .65, (0,0,255), 2)
                        cv.imshow(window, view)
                if cv.waitKey(1) & 255 in (ord('q'), 27):
                    break
                if cv.getWindowProperty(window, cv.WND_PROP_VISIBLE) < 1:
                    break
                time.sleep(.002)
        finally:
            if folder and vectors:
                path = save_session(np, folder, vectors)
                print('Session enregistrée :', path, '(', len(vectors), 'exemples )')
            cv.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--setup', action='store_true')
    actions.add_argument('--list', action='store_true')
    actions.add_argument('--delete', metavar='PRENOM')
    actions.add_argument('--enroll', metavar='PRENOM')
    actions.add_argument('--camera-test', action='store_true')
    parser.add_argument('--data', type=Path, default=Path.home()/'visages_connus')
    parser.add_argument('--models', type=Path, default=Path.home()/'modeles_visages')
    parser.add_argument('--camera', default='/dev/video0')
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int)
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--raw', action='store_true', help='YUYV si la webcam refuse MJPEG')
    parser.add_argument('--mjpeg', action='store_true', help='Compatibilité : MJPEG est déjà le défaut')
    parser.add_argument('--preview-width', type=int, default=640)
    parser.add_argument('--analysis-width', type=int, default=320)
    parser.add_argument('--detect-fps', type=float, default=2)
    parser.add_argument('--max-age', type=float, default=3, help='Expiration des cadres affichés en secondes')
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--threshold', type=float, default=.40, help='Similarité SFace : plus élevé = plus strict')
    parser.add_argument('--margin', type=float, default=.05, help='Écart minimal entre deux personnes')
    parser.add_argument('--min-sharpness', type=float, default=35)
    parser.add_argument('--scores', action='store_true')
    args = parser.parse_args()
    if min(args.width, args.height or 1, args.fps, args.preview_width, args.analysis_width, args.samples) <= 0 or args.detect_fps <= 0 or args.max_age <= 0:
        parser.error('Dimensions, cadences et nombre d’exemples doivent être positifs.')
    if not 0 < args.threshold < 1 or not 0 <= args.margin < 1 or args.min_sharpness < 0:
        parser.error('Seuil SFace attendu entre 0 et 1 (ancien seuil LBPH incompatible).')
    args.data, args.models = args.data.expanduser(), args.models.expanduser()
    if args.delete:
        delete_person(args.data, args.delete)
        return
    if args.list:
        list_people(args.data)
        return
    if args.setup:
        setup_models(args.models)
        return
    if args.enroll:
        person_path(args.data, args.enroll)
    import cv2 as cv
    import numpy as np
    cv.setNumThreads(1)
    if not args.camera_test and not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        raise RuntimeError('Ouvre ce programme dans un terminal du bureau du Pi (écran ou VNC). Depuis SSH, utilise --camera-test.')
    worker = None
    if not args.camera_test:
        if not hasattr(cv, 'FaceDetectorYN') or not hasattr(cv, 'FaceRecognizerSF'):
            raise RuntimeError('OpenCV incompatible. Installe python3-opencv de Raspberry Pi OS récent (4.8+).')
        engine = Engine(cv, np, args.models, args.analysis_width)
        gallery = Gallery(np, args.data, args.threshold, args.margin)
        worker = Worker(engine, gallery, bool(args.enroll))
    camera = None
    try:
        camera = open_camera(cv, args)
        if args.camera_test:
            start, first, last = time.monotonic(), None, None
            while time.monotonic()-start < 12:
                item, error, _ = camera.snapshot()
                if error:
                    raise RuntimeError(error)
                if item and time.monotonic()-start > 2:
                    first = first or item
                    last = item
                time.sleep(.01)
            if first and last and last[1] > first[1]:
                print(f'Cadence mesurée : {(last[0]-first[0])/(last[1]-first[1]):.1f} FPS')
            else:
                raise RuntimeError('Aucune image reçue.')
            print('Formats disponibles : v4l2-ctl --device=' + args.camera + ' --list-formats-ext')
        else:
            run_gui(cv, np, args, camera, worker)
    finally:
        if camera:
            camera.close()
        if worker:
            worker.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print('Erreur :', exc, flush=True)
        raise SystemExit(1)
