import py_compile

filepath = '/home/apps/web-b-revendedores/connection_api.py'

with open(filepath) as f:
    c = f.read()

old = "pins_texto = '\n'.join(pins_list)"
new = "pins_texto = '\\n'.join(pins_list)"

if old in c:
    c = c.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(c)
    py_compile.compile(filepath, doraise=True)
    print('Syntax OK - line fixed')
else:
    print('Old pattern not found - checking what is there')
    # Find the pins_texto lines
    for i, line in enumerate(c.split('\n'), 1):
        if 'pins_texto' in line:
            print(f'Line {i}: {repr(line)}')
