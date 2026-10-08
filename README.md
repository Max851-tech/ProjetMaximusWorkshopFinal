# Reconnaissance de visages sur Raspberry Pi 3 B+ et acces noVNC par SSH

Ce dossier rassemble le script `reconnaissance_visage_2.py`, l'installation de ses dependances, la configuration de noVNC et le lanceur Windows qui ouvre le bureau de la Raspberry au travers d'un tunnel SSH chiffre.

Le script dans `src/` est une copie exacte de la version deja utilisee : detection YuNet, reconnaissance SFace, enregistrement des personnes, fenetre OpenCV et alarme sonore en cas de visage inconnu. Les modeles et les personnes deja enregistrees dans ton dossier personnel sont reutilises.

Le bureau noVNC devient disponible au demarrage du Pi. Le lanceur Windows attend que le Pi soit joignable, etablit SSH et ouvre le navigateur. La reconnaissance se lance ensuite depuis un terminal du bureau noVNC ; son demarrage automatique n'est pas installe par ce projet.

## 1. Structure et fichiers

| Chemin | Role |
|---|---|
| `src/reconnaissance_visage_2.py` | Script original de reconnaissance et d'alarme |
| `scripts/raspberry/installer_reconnaissance.sh` | Dependances, groupes video/audio et modeles |
| `scripts/raspberry/lancer_reconnaissance.sh` | Lance le script en transmettant les arguments |
| `scripts/raspberry/installer_novnc.sh` | Wi-Fi automatique, bureau automatique, SSH et noVNC |
| `scripts/raspberry/modifier_wayvnc.py` | Sauvegarde et adaptation de la configuration WayVNC |
| `scripts/raspberry/diagnostic.sh` | Informations reseau, services, webcam, alimentation et journaux |
| `scripts/windows/Demarrer_noVNC.ps1` | Attend le Pi, cree le tunnel et ouvre le navigateur |
| `scripts/windows/Installer_demarrage_Windows.ps1` | Raccourci dans le demarrage de ta session Windows |
| `config/novnc.service` | Copie lisible du service systemd pour l'utilisateur pi-os |
| `config/wayvnc-ssh.conf.example` | Extrait des options WayVNC appliquees par l'installateur |
| `docs/FONCTIONNEMENT.md` | Organisation du code et fonctionnement de la reconnaissance |
| `docs/DEPANNAGE.md` | Diagnostic SSH, noVNC, HDMI, webcam et redemarrages |

## 2. Configuration utilisee

| Element | Valeur / explication |
|---|---|
| Materiel | Raspberry Pi 3 B+, webcam USB, Windows 11 |
| OS Pi | Raspberry Pi OS recent avec bureau Wayland et le service WayVNC de la distribution |
| Wi-Fi | `iphone_hichem` |
| Mot de passe Wi-Fi | A saisir avec `nmcli --ask` si besoin ; absent de ce dossier |
| Utilisateur Pi | `pi-os` |
| Adresse actuelle Pi | `172.20.10.3` ; elle peut changer avec le partage iPhone |
| SSH | Port 22 ; authentification par cle Ed25519 pour le lanceur |
| VNC sur Pi | `127.0.0.1:5900`, seulement accessible localement |
| noVNC sur Pi | `127.0.0.1:6080`, seulement accessible localement |
| noVNC sur Windows | `http://127.0.0.1:16080/vnc.html` |
| Port de verification Windows | `127.0.0.1:16081`, teste le protocole VNC avant ouverture de la page |
| Cle privee Windows | `%USERPROFILE%\.ssh\id_ed25519_novnc` |
| Modeles | `~/modeles_visages` sur la Raspberry |
| Visages enregistres | `~/visages_connus` sur la Raspberry |
| Webcam par defaut | `/dev/video0` |

Les fichiers de modeles ONNX, les empreintes personnelles et les cles privees ne sont pas inclus. `--setup` telecharge les modeles et verifie leur empreinte SHA-256. La reconnaissance fonctionne ensuite localement, sans API externe.

## 3. Comprendre dans quel terminal executer une commande

| Invite visible | Machine | Commandes |
|---|---|---|
| `PS C:\Users\h-ben>` | Windows | `scp`, connexion `ssh`, scripts `.ps1`, `ssh-add` |
| `pi-os@Pi-os:~ $` | Raspberry, accessible en SSH | Installation Linux, `systemctl`, `nmcli`, diagnostic |
| Terminal ouvert DANS le bureau noVNC | Bureau graphique de la Raspberry | Reconnaissance avec fenetre et enregistrement des visages |

Ne lance pas une commande contenant `$env:USERPROFILE` depuis le terminal Linux. Une connexion SSH ordinaire ne donne pas l'environnement graphique necessaire a la fenetre OpenCV.

## 4. Copier le projet

Sur Windows, telecharge `Projet_Raspberry_Reconnaissance.zip` dans Telechargements. Dans PowerShell normal :

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Projet_Raspberry_Reconnaissance.zip" -DestinationPath "$env:USERPROFILE\Raspberry-Projet" -Force
scp "$env:USERPROFILE\Downloads\Projet_Raspberry_Reconnaissance.zip" pi-os@172.20.10.3:/home/pi-os/
ssh pi-os@172.20.10.3
```

Sur la Raspberry, dans la connexion SSH :

```bash
sudo apt install -y unzip
cd ~
unzip -o Projet_Raspberry_Reconnaissance.zip
cd ~/Projet_Raspberry_Reconnaissance
```

La premiere connexion SSH doit verifier l'identite du Pi. Compare l'empreinte presentee par Windows avec `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` execute directement sur le Pi. Ne supprime pas automatiquement une alerte de changement de cle.

## 5. Installer la reconnaissance

Dans le terminal de la Raspberry, en utilisateur normal, execute :

```bash
cd ~/Projet_Raspberry_Reconnaissance
bash scripts/raspberry/installer_reconnaissance.sh
```

L'installateur utilise les paquets Raspberry Pi OS : `python3-opencv`, `python3-numpy`, `alsa-utils`, `pulseaudio-utils` et `v4l-utils`. Il ajoute ton utilisateur aux groupes `video` et `audio`, verifie OpenCV 4.8+ et ses API de reconnaissance, puis prepare les modeles. Internet est necessaire pour cette installation. Reouvre ta session ou redemarre plus tard pour les nouveaux groupes.

Les modeles sont installes dans `~/modeles_visages`. Si les modeles sont deja presents et valides, ils ne sont pas telecharges de nouveau. Les donnees personnelles dans `~/visages_connus` sont conservees.

## 6. Configurer le Wi-Fi et noVNC

Si l'installation noVNC precedente fonctionne deja, cette etape peut etre sautee. Dans ce cas, utilise les diagnostics pour verifier les services avant de les reconfigurer.

Active le partage iPhone avant de demarrer le Pi et connecte le PC au meme Wi-Fi. Le Pi doit deja etre connecte a `iphone_hichem` pour l'installateur. Si ce n'est pas le cas, execute depuis son bureau local :

```bash
sudo nmcli --ask device wifi connect "iphone_hichem" name "PartageTelephone"
```

Entre le mot de passe du partage uniquement lorsqu'il est demande. Un changement de Wi-Fi peut interrompre SSH. Ne relance pas cette commande si le Pi est deja connecte correctement.

Depuis SSH, configure ensuite :

```bash
cd ~/Projet_Raspberry_Reconnaissance
bash scripts/raspberry/installer_novnc.sh
sudo reboot
```

L'installateur :

1. Verifie que le profil Wi-Fi actif correspond a `iphone_hichem`, puis active `autoconnect`, une priorite de 100 et les tentatives illimitees.
2. Active SSH et l'ouverture automatique de ta session de bureau au demarrage (`B4`).
3. Sauvegarde `/etc/wayvnc/config` avant modification ; applique `address=127.0.0.1`, `port=5900` et `enable_auth=false` tout en conservant les autres options.
4. Installe `/etc/systemd/system/novnc.service` et active son demarrage automatique.

La priorite Wi-Fi s'applique lors du choix d'une connexion ; elle ne remplace pas un autre reseau deja actif. Le mot de passe memorise reste gere par NetworkManager sur le Pi.

L'absence d'authentification VNC locale evite une seconde saisie pour le navigateur. L'acces distant est authentifie et chiffre par SSH. Les comptes locaux sur le Pi peuvent joindre les ports locaux. La session graphique auto-ouverte est egalement accessible a une personne presente devant le Pi.

Apres le reboot, reconnecte-toi en SSH et verifie :

```bash
sudo systemctl status ssh wayvnc novnc --no-pager
sudo ss -ltnp | grep -E ':5900|:6080'
```

Les services doivent etre actifs ; les deux ports doivent ecouter seulement sur `127.0.0.1`. Le message websockify « No SSL/TLS support » est attendu : le transport entre les machines est chiffre par SSH, pas par un certificat HTTPS.

## 7. Configurer l'authentification automatique Windows

Si tu as deja obtenu `Connexion_OK` sans demande de mot de passe avec ta cle, conserve cette cle et passe a la section 8. Ne la recree pas.

Dans PowerShell normal, pour une premiere installation :

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519_novnc" -C "noVNC-Pi"
Get-Content "$env:USERPROFILE\.ssh\id_ed25519_novnc.pub" | ssh pi-os@172.20.10.3 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
```

Choisis une phrase secrete pour la cle. N'ecrase pas une cle existante. La commande de copie demande le mot de passe de `pi-os`, qui est distinct du mot de passe Wi-Fi et de la phrase secrete de la cle.

Dans une fenetre PowerShell en administrateur, sous ton compte Windows habituel :

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic
Start-Service ssh-agent
```

Dans PowerShell normal :

```powershell
ssh-add "$env:USERPROFILE\.ssh\id_ed25519_novnc"
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_novnc" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes pi-os@172.20.10.3 'echo Connexion_OK'
```

Charge la cle avec sa phrase secrete. Le test doit afficher `Connexion_OK` sans demande interactive avant de continuer. Aucun mot de passe n'est enregistre dans les scripts Windows.

## 8. Ouvrir automatiquement noVNC sur Windows

Si l'ancien lanceur tourne, arrete-le avec Ctrl+C dans sa fenetre avant d'utiliser celui de ce projet. Le nouveau raccourci remplace le raccourci precedent du meme nom.

Dans PowerShell normal :

```powershell
cd "$env:USERPROFILE\Raspberry-Projet\Projet_Raspberry_Reconnaissance\scripts\windows"
Get-ChildItem . -Filter *.ps1 | Unblock-File
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\Installer_demarrage_Windows.ps1
```

Cela installe `Bureau Raspberry par SSH.lnk` dans le demarrage de ta session et lance immediatement le programme d'attente. Garde sa fenetre active, eventuellement reduite. Le PC doit etre allume, non en veille, session ouverte et sur le meme reseau. Ne deplace plus le dossier Windows ensuite.

Le navigateur ouvre :

```text
http://127.0.0.1:16080/vnc.html?autoconnect=true&reconnect=true&reconnect_delay=3000&resize=scale
```

Le lanceur garde les deux ports locaux sur `127.0.0.1`, utilise seulement la cle indiquee, refuse les cles serveur inconnues/changees, verifie le protocole VNC et la page noVNC, puis ouvre le navigateur. Apres une interruption SSH, il essaie de nouveau et rouvre la page quand le Pi revient. Il ne commande aucun reboot du Pi.

Pour relancer manuellement le lanceur :

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\Demarrer_noVNC.ps1
```

Si l'adresse du Pi change, arrete le lanceur puis recree le raccourci en adaptant l'IP :

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\Installer_demarrage_Windows.ps1 -PiAddress NOUVELLE_IP
```

## 9. Utiliser le script de reconnaissance

Les commandes avec fenetre doivent etre lancees dans un terminal du BUREAU noVNC, pas dans PowerShell ni dans une session SSH simple. Ferme VLC et tout autre logiciel qui utilise la webcam.

```bash
cd ~/Projet_Raspberry_Reconnaissance
bash scripts/raspberry/lancer_reconnaissance.sh --enroll Hichem --samples 30
```

Presente un seul visage, assez proche, bien eclaire, et varie doucement l'angle/la distance. Apres l'enregistrement :

```bash
bash scripts/raspberry/lancer_reconnaissance.sh
```

Q ou Echap ferme la fenetre. Lister les personnes fonctionne aussi depuis SSH :

```bash
bash scripts/raspberry/lancer_reconnaissance.sh --list
```

Pour supprimer volontairement tous les exemples d'une personne :

```bash
bash scripts/raspberry/lancer_reconnaissance.sh --delete Hichem
```

La suppression est definitive pour le dossier de cette personne ; redemarre ensuite une surveillance deja en cours pour recharger la galerie.

### Reglages principaux du script

| Option | Defaut | Effet |
|---|---|---|
| `--camera` | `/dev/video0` | Choisir la webcam |
| `--width` / `--height` | 640 / hauteur 4:3 calculee | Taille demandee a la webcam |
| `--fps` | 30 | Cadence de capture demandee, sans garantie materielle |
| `--raw` | Desactive | Demander YUYV au lieu de MJPEG |
| `--preview-width` | 640 | Largeur maximale de l'apercu |
| `--analysis-width` | 320 | Taille de l'image utilisee pour la detection |
| `--detect-fps` | 2 | Frequence maximale demandee pour soumettre des analyses |
| `--max-age` | 3 secondes | Expiration des anciens resultats affiches |
| `--threshold` | 0.40 | Similarite minimale SFace ; plus grand = plus strict |
| `--margin` | 0.05 | Ecart minimal entre les deux meilleures identites |
| `--scores` | Desactive | Afficher les scores de similarite |
| `--samples` | 30 | Nombre d'exemples vises pendant un enregistrement |
| `--data` | `~/visages_connus` | Dossier des personnes |
| `--models` | `~/modeles_visages` | Dossier des modeles |

Exemple pour demander une capture moins lourde sur la Pi 3 B+ :

```bash
bash scripts/raspberry/lancer_reconnaissance.sh --fps 15 --detect-fps 1 --scores
```

Exemple pour tester la webcam depuis SSH, sans fenetre :

```bash
bash scripts/raspberry/lancer_reconnaissance.sh --camera-test
```

L'alarme sonore est jouee sur la sortie audio de la Raspberry. Ce projet transporte le bureau via noVNC ; il n'ajoute pas de diffusion audio au navigateur.

## 10. Controle, limites et references

La copie du script original a ete comparee par SHA-256. Les scripts Bash et Python ont ete controles pour leur syntaxe. Le lancement depuis un chemin contenant des espaces et la transmission des arguments ont ete verifies avec un interpreteur simule.

Le fonctionnement complet depend du materiel : webcam, modeles, audio, bureau Wayland et reseau. Le probleme SSH/headless signale dans la conversation n'a pas ete diagnostique a distance et sa resolution n'est pas garantie par ce dossier. Les scripts Windows n'ont pas pu etre executes dans l'environnement Linux de preparation.

Les seuils doivent etre ajustes et testes avec tes exemples. Les cadences sont des valeurs demandees, pas des performances garanties ; les scores SFace sont des similarites et non des pourcentages de certitude.

References utiles :

- Raspberry Pi : https://www.raspberrypi.com/documentation/computers/remote-access.html
- Configuration Raspberry Pi : https://www.raspberrypi.com/documentation/computers/configuration.html
- WayVNC et tunnel SSH : https://github.com/any1/wayvnc/blob/master/README.md
- noVNC et reconnexion : https://github.com/novnc/noVNC/blob/master/docs/EMBEDDING.md
- Cles SSH Windows : https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement
- OpenCV YuNet/SFace : https://docs.opencv.org/4.13.0/d0/dd4/tutorial_dnn_face.html
