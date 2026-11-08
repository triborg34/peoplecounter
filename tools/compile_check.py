import pathlib, py_compile, traceback
root = pathlib.Path('D:/pro')
bad = []
for p in sorted(root.rglob('*.py')):
    if any(part in ('.venv','__pycache__','build','dist') for part in p.parts):
        continue
    try:
        compile(p.read_text(encoding='utf-8'), str(p), 'exec')
    except SyntaxError as e:
        bad.append((str(p).replace('D:\\pro\\',''), e.lineno, e.msg, (e.text or '').strip()))
for b in bad:
    print('SYNTAX ERROR %s:%s  %s  |  %s' % b)
print('checked files, errors:', len(bad))
