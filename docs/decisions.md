# Decisions Log

## 2026-09-14 - Monorepo with 2 folders, not two repos 
Considered splitting infrastcuture and model code into seperate repos, but chose 1 po with `infrastructure/` and `models/` as top level folders instead, since this is just a solo project. Easy to split into two repos later if collaborators join or folders genuinely start straining against each other.

## 2026-09-21 — Renamed container/database for clarity
Originally named the container `bank-db` and the database `bank`, too
visually similar and a repeated source of confusion during debugging.
Renamed to `bank_container` (container) and `bank_db` (database), using
underscores consistently to avoid SQL identifier quoting issues that
hyphens would introduce in database names.