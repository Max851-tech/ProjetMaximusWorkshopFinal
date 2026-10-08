# Depannage : reseau, bureau et reconnaissance

Le Pi doit etre accessible en SSH avant de diagnostiquer noVNC. Un bureau indisponible ne prouve pas que le Pi est arrete.

## SSH : Connection timed out

Ce message signifie que le PC n'obtient pas de connexion au port 22 de l'adresse cible. Ce n'est pas encore une erreur de mot de passe.

Sur Windows, verifier que le Wi-Fi actif est `iphone_hichem`, puis :

```powershell
ipconfig
Test-NetConnection 172.20.10.3 -Port 22
ssh pi-os@Pi-os.local
```

Si le nom fonctionne mais pas l'ancienne IP, lire l'adresse courante avec `hostname -I` depuis SSH. Si rien ne fonctionne, utiliser temporairement HDMI et un clavier, puis executer sur le Pi :

```bash
hostname -I
nmcli device status
sudo systemctl status ssh --no-pager
```

Si SSH est arrete : `sudo systemctl enable --now ssh`. Si le Wi-Fi est deconnecte, reconnecter le partage depuis le bureau local avec `sudo nmcli --ask device wifi connect "iphone_hichem"`. Ne pas enchaîner les changements de reseau depuis une session SSH dont on depend.

## Le Pi demarre-t-il vraiment sans HDMI ?

Sur la Pi 3 B+, le voyant rouge PWR indique l'alimentation et le voyant vert ACT l'activite de la carte microSD. Le vert eteint au repos peut etre normal. Les voyants ne prouvent pas que SSH est pret.

Une connexion SSH reussie puis `uptime` confirme que Linux tourne. Retirer HDMI ne devrait pas arreter SSH ; la connexion Wi-Fi, l'IP et l'alimentation restent a verifier si SSH disparait.

## La Raspberry ou le navigateur semble redemarrer en boucle

Arreter d'abord le lanceur Windows avec Ctrl+C pour eviter l'ouverture repetee d'onglets. Dans SSH :

```bash
uptime
cat /proc/sys/kernel/random/boot_id
```

Comparer ces valeurs apres une coupure : un nouvel identifiant de boot indique un vrai reboot ; le meme identifiant avec un uptime croissant indique plutot une coupure reseau/bureau.

Pour isoler noVNC sans arreter SSH :

```bash
sudo systemctl disable --now novnc
sudo systemctl stop wayvnc
vcgencmd get_throttled
sudo journalctl -b -1 -n 80 --no-pager
```

Le journal du boot precedent peut etre absent si les journaux ne sont pas persistants. Ne pas modifier la carte SD ni reflasher l'OS avant d'avoir collecte les observations utiles.

Pour retablir les services :

```bash
sudo systemctl start wayvnc
sudo systemctl enable --now novnc
```

Si le Pi redemarre reellement, essayer une alimentation adaptee a la Pi 3 B+ (5 V / 2,5 A) et verifier sans les accessoires USB, notamment la webcam. Une sous-tension est une hypothese a verifier, pas un diagnostic automatique.

## noVNC fonctionne avec HDMI mais pas sans HDMI

Verifier separement SSH, les services et la session graphique :

```bash
sudo systemctl status display-manager wayvnc novnc --no-pager -l
loginctl list-sessions
sudo journalctl -b -u wayvnc -u novnc -u lightdm -n 80 --no-pager
```

WayVNC a besoin d'un bureau Wayland et d'une sortie utilisable pour partager l'ecran. Une ecoute VNC active ne garantit pas que le compositeur fournit une image. Rebrancher temporairement HDMI permet de distinguer ce probleme de celui du reseau.

Le projet ne force pas automatiquement un ecran virtuel et ne modifie pas `/boot/firmware/cmdline.txt`. Le reglage de resolution VNC classique de raspi-config peut ne pas s'appliquer sous Wayland. Il faut identifier la configuration du bureau avant de choisir une configuration headless adaptee.

## Erreur de cle SSH

Si `Connexion_OK` echoue :

- `Permission denied (publickey)` : verifier la cle dans `~/.ssh/authorized_keys` et `ssh-add -l` sur Windows.
- `Host key verification failed` : refaire une connexion manuelle et verifier l'empreinte serveur sur le Pi.
- `REMOTE HOST IDENTIFICATION HAS CHANGED` : confirmer l'identite du Pi et un eventuel changement/reinstallation avant de remplacer une entree connue.

Ne pas desactiver `StrictHostKeyChecking` dans le lanceur. Le mot de passe Wi-Fi ne sert pas a se connecter a SSH.

## noVNC ne s'ouvre pas sur Windows

Depuis le dossier `scripts/windows`, lire :

```powershell
Get-Content .\derniere_erreur_ssh.log
```

La page locale est `http://127.0.0.1:16080/vnc.html`. Ce n'est pas l'adresse IP du Pi : le port local correspond au tunnel SSH.

Si le lanceur annonce qu'il est deja actif, restaurer sa fenetre existante. Pour un nouveau lancement, arreter l'ancien avec Ctrl+C. Si les ports 16080/16081 sont occupes, identifier le tunnel deja actif ; ne pas tuer au hasard d'autres processus Windows.

Pour retirer le demarrage automatique : Win+R, `shell:startup`, puis supprimer `Bureau Raspberry par SSH.lnk`. Le dossier contenant le script doit rester a l'emplacement utilise lors de l'installation du raccourci.

## Webcam et fenetre OpenCV

Fermer VLC et les autres programmes qui ouvrent la webcam. Depuis SSH :

```bash
v4l2-ctl --list-devices
bash ~/Projet_Raspberry_Reconnaissance/scripts/raspberry/lancer_reconnaissance.sh --camera-test
```

Si la webcam correspond a `/dev/video2`, passer `--camera /dev/video2`. Verifier les formats disponibles avec `v4l2-ctl --device=/dev/video0 --list-formats-ext`. Utiliser `--raw` si la webcam refuse le mode MJPEG.

Si le script demande un bureau graphique, lancer la surveillance depuis un terminal DANS le bureau noVNC. Ne pas inventer une valeur `DISPLAY` pour masquer cette erreur.

## Bip absent ou modeles manquants

Le bip se joue sur le Pi ; verifier sa sortie audio, les groupes et les paquets `alsa-utils`/`pulseaudio-utils`. noVNC ne transporte pas le son dans cette configuration.

Pour preparer de nouveau les modeles depuis SSH :

```bash
bash ~/Projet_Raspberry_Reconnaissance/scripts/raspberry/lancer_reconnaissance.sh --setup
```

Pour collecter un diagnostic d'ensemble, sans changer la configuration :

```bash
bash ~/Projet_Raspberry_Reconnaissance/scripts/raspberry/diagnostic.sh
```
