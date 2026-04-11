import re

with open('game/main.py', 'r', encoding='utf-8') as f:
    content = f.readlines()

for i, line in enumerate(content):
    if any(ord(c) > 127 for c in line):
        print(f"{i+1}: {line.strip()}")
