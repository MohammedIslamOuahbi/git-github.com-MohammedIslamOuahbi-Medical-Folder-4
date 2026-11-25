# Deploiement LAN Tauri + PostgreSQL

Cette application utilise une architecture centralisee :

```text
Postes clients -> HTTP -> FastAPI -> SQLAlchemy -> PostgreSQL actif du poste serveur
```

Le meme installateur est utilise sur tous les postes. PostgreSQL doit etre installe sur tous les postes, mais en mode client il reste inutilise par l'application.

Les postes clients ne se connectent jamais directement a PostgreSQL.

## Sur chaque poste

1. Installez PostgreSQL.
2. Installez la meme application desktop Medical Folder.
3. Lancez l'application.
4. Choisissez le mode du poste : `Mode Serveur` ou `Mode Client`.

## Poste serveur

1. Verifiez que PostgreSQL est installe sur ce poste.
2. Verifiez que le service Windows PostgreSQL est demarre.
3. Au premier demarrage, choisissez `Mode Serveur`.
4. Renseignez les parametres PostgreSQL locaux.
5. Renseignez l'hote et le port FastAPI, par defaut `0.0.0.0:8000`.
6. L'application cree ou reutilise la base applicative, applique Alembic, puis ecrit le `backend.env` runtime dans Local App Data.
7. Autorisez uniquement le port FastAPI dans le pare-feu Windows.
8. Verifiez les endpoints :

```text
http://localhost:8000/health
http://localhost:8000/health/identity
http://localhost:8000/health/database
```

Le serveur FastAPI ecoute en mode serveur sur l'hote configure, generalement `0.0.0.0:8000`.
Les postes clients utilisent l'URL LAN affichee par l'application, par exemple :

```text
http://192.168.1.10:8000
```

## Poste client

1. Verifiez que PostgreSQL est installe si ce PC doit pouvoir devenir serveur lors d'une autre mission.
2. Choisissez `Mode Client`.
3. Saisissez uniquement l'URL FastAPI du poste serveur.
4. Testez la connexion.
5. Connectez-vous avec un compte utilisateur applicatif.

Meme si PostgreSQL est installe localement, le poste client ne l'utilise pas, ne demarre pas le backend local et ne recoit jamais de mot de passe PostgreSQL.

## Sites sans internet

Exemple :

```text
PC docteur
- Mode Serveur
- PostgreSQL local actif
- FastAPI local
- Hotspot Windows ou reseau LAN
- URL LAN : http://192.168.137.1:8000

PC assistants
- Mode Client
- PostgreSQL local inutilise
- URL serveur : http://192.168.137.1:8000
```

Internet n'est pas requis. Un reseau local, un routeur ou un hotspot Windows suffit.

## Pare-feu et reseau

- Ouvrez uniquement le port TCP FastAPI configure sur le poste serveur, generalement `8000`.
- Gardez le port PostgreSQL `5432` prive et non necessaire aux postes clients.
- N'utilisez pas l'URL Vite `:5173` en production Tauri.
- L'endpoint `/health/identity` confirme que l'URL pointe bien vers le serveur medical attendu.

## Avertissement important

Meme si PostgreSQL est installe sur tous les postes, un seul poste doit etre utilise comme serveur actif pendant une mission. Les postes clients se connectent uniquement a FastAPI et n'utilisent pas leur base PostgreSQL locale.

Ne documentez pas de vrais mots de passe et ne copiez pas le `DATABASE_URL` de production dans le frontend, le depot Git ou les postes clients.
