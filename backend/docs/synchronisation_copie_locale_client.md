# Synchronisation Serveur vers Client

## Pendant le travail d'equipe

```text
Client -> FastAPI du Serveur -> PostgreSQL du Serveur
```

Le serveur reste la source principale. Les postes clients utilisent l'API FastAPI du serveur pour les operations normales.

## En fin de travail

Un poste client peut demander un export applicatif au serveur :

```text
PostgreSQL Serveur -> FastAPI -> Package JSON verifie -> Poste Client
Poste Client -> Import transactionnel -> PostgreSQL local de copie
```

La direction est strictement Serveur vers Client. Aucune donnee locale n'est envoyee vers le serveur dans cette version.

## Donnees exportees

L'export utilise une liste autorisee de tables applicatives : utilisateurs de reference, permissions, societes, branches, sites, campagnes, travailleurs, visites medicales, tests, prescriptions, certificats, espaces de travail et lignes d'import.

Les champs sensibles sont exclus :

- `password_hash`
- `workspace_password_hash`
- tokens
- `DATABASE_URL`
- `SECRET_KEY`
- identifiants PostgreSQL

## Curseur de synchronisation

Le curseur durable est fourni par le journal applicatif `client_sync_changes`.
Son identifiant global croissant est cree dans la meme transaction que les modifications applicatives suivies.
Il remplace les curseurs internes PostgreSQL comme `xmin`, qui ne sont pas adaptes comme contrat durable entre deux bases.

Le serveur retourne :

- `server_id`
- `from_cursor`
- `to_cursor`
- `schema_version`
- `record_counts`
- `checksum_sha256`
- `data`
- `tombstones`

Un client qui n'a pas de curseur effectue une synchronisation initiale avec un snapshot complet et un `to_cursor` stable. Les synchronisations suivantes utilisent `after_cursor` pour recevoir uniquement les changements posterieurs.

## Restrictions importantes

- Le serveur reste la source de verite.
- La synchronisation est Serveur vers Client uniquement.
- Les modifications locales du client ne sont pas envoyees.
- Les clients ne se connectent jamais directement au PostgreSQL du serveur.
- Ne lancez pas plusieurs bases actives independantes pendant une mission.
- La copie PostgreSQL locale n'est pas encore utilisee par les ecrans normaux de l'application.
- Cette version ne promet pas une consultation locale hors ligne complete.

## Import local

L'import transactionnel dans la base PostgreSQL locale du client est controle par Tauri/Rust avec une configuration separee `client-sync.env`.

- Le fichier `client-sync.env` est resolu uniquement par Rust dans Local App Data.
- Les identifiants PostgreSQL locaux ne sont pas stockes dans `localStorage`.
- Le schema local est initialise par Alembic contre la base locale de copie uniquement.
- Le package exporte est verifie avant import.
- Les entites inconnues et les champs inconnus sont refuses ou ignores selon la liste autorisee.
- Le curseur local n'est avance qu'apres commit reussi.
- Les ecrans normaux restent connectes au FastAPI du serveur.

## Limites actuelles

- Les pieces jointes et fichiers generes ne sont pas encore synchronises comme fichiers physiques.
- Le mode consultation locale en lecture seule n'est pas active dans cette phase.
- Il n'y a pas de synchronisation Client vers Serveur.
- Il n'y a pas de resolution de conflits bidirectionnelle.
