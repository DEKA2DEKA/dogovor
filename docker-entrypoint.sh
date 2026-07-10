#!/bin/sh
alembic upgrade head
exec python app.py
