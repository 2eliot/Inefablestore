#!/usr/bin/env python3
"""Add direct_to_pin column to store_packages"""
import psycopg

c = psycopg.connect('postgresql://inefable_user:InefablePg2026@127.0.0.1:5432/inefablestore')
c.execute('ALTER TABLE store_packages ADD COLUMN IF NOT EXISTS direct_to_pin INTEGER DEFAULT 0')
c.commit()
c.close()
print('OK: direct_to_pin column added')
