# Fonctionnement de reconnaissance_visage_2.py

Le script utilise la webcam de la Raspberry, detecte les visages avec YuNet et compare leurs empreintes avec les personnes enregistrees a l'aide de SFace. L'apercu et l'analyse ne travaillent pas a la meme cadence : cela permet de conserver une video plus fluide lorsque la reconnaissance est lente.

## Organisation du code

| Element | Fonction |
|---|---|
| `setup_models()` | Telecharge les deux modeles ONNX et verifie leur SHA-256 |
| `Gallery` | Charge les sessions `.npz` et compare les vecteurs SFace aux personnes |
| `Engine` | Detecte les visages, aligne les recadrages et extrait les vecteurs |
| `Camera` | Lit la webcam dans un thread ; conserve seulement la derniere image |
| `Worker` | Analyse dans un thread distinct, avec une seule image en attente |
| `AlertGate` | Evite de sonner a chaque image ; gere confirmations et delai entre alarmes |
| `run_gui()` | Dessine les cadres, noms, scores, statistiques et le bandeau d'alerte |
| `save_session()` | Enregistre les empreintes collectees dans une session `.npz` |
| `main()` | Lit les options, initialise les composants et les ferme a la sortie |

## Detection et identification

1. La webcam est ouverte avec OpenCV/V4L2, en demandant MJPEG 640 x 480 a 30 images/s par defaut.
2. La detection utilise une image reduite, de largeur 320 par defaut. Les coordonnees et reperes sont remappes sur l'image de capture.
3. SFace aligne chaque visage et produit un vecteur de 128 valeurs, normalise.
4. La galerie calcule la similarite avec les references. Pour chaque personne, le score utilise la moyenne des deux meilleurs exemples, ou le seul exemple disponible.
5. Le nom est retenu si le score atteint le seuil et si la meilleure identite est suffisamment distincte de la suivante. Le suivi attend aussi deux analyses coherentes avant l'etat « known ».
6. Les resultats anciens expirent selon `--max-age` ; ils ne restent pas affiches indefiniment.

Les etats internes sont `known`, `checking` et `unknown`. Le cadre est vert pour une personne reconnue et orange pour les autres etats.

## Enregistrer une personne

`--enroll Hichem --samples 30` cree une session SFace dans `~/visages_connus/Hichem/`.

Le script recherche un seul visage, suffisamment grand, net et correctement eclaire. Il espace les exemples et evite de stocker uniquement des vecteurs presque identiques. Si la fenetre est fermee avant le nombre vise, les exemples deja collectes sont sauvegardes quand meme.

Les anciennes images PNG LBPH peuvent rester dans les dossiers. Elles ne sont pas converties automatiquement en references SFace : il faut reenregistrer les personnes si seuls ces anciens exemples existent.

## Alarme

L'alarme demande plusieurs observations d'un visage inconnu. Le code utilise trois mises a jour successives, un delai entre alarmes de 30 secondes et une absence de 3 secondes pour reinitialiser la presence.

Lorsque l'alarme est declenchee :

- Le terminal affiche `ALERTE : visage inconnu`.
- Une bordure rouge et un bandeau d'alerte apparaissent pendant 5 secondes.
- Un bip est genere temporairement et joue sur la Raspberry avec `paplay`, puis `aplay` en secours.

Le son n'est pas envoye dans le flux noVNC. Si aucun lecteur audio ne fonctionne, le script indique que le bip est indisponible.

## Configuration et donnees

Les options de reconnaissance sont des arguments de ligne de commande. Le script original ne charge pas de fichier `.env`, n'expose pas d'API HTTP et ne lit pas la configuration noVNC.

Les empreintes personnelles sont stockees dans des fichiers `.npz`. Les modeles et les donnees sont situes dans le dossier personnel de l'utilisateur qui lance le script ; c'est pourquoi les commandes de lancement utilisent l'utilisateur normal et non `sudo python3`.

Les options `--setup`, `--list`, `--delete` et `--camera-test` sont utilisables depuis SSH sans bureau. La surveillance et `--enroll` demandent une session graphique.
