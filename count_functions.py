import re

files = ['config.py', 'rate_limit.py', 'ffmpeg_utils.py', 'bot.py']
total = 0
all_functions = {}

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Функции верхнего уровня
    funcs = re.findall(r'^(?:async )?def (\w+)\(', content, re.MULTILINE)
    # Методы классов (с отступом)
    methods = re.findall(r'^    (?:async )?def (\w+)\(', content, re.MULTILINE)
    
    all_funcs = list(set(funcs + methods))
    all_funcs.sort()
    all_functions[f] = all_funcs
    
    print(f'\n{"="*60}')
    print(f'{f}: {len(all_funcs)} функций')
    print("="*60)
    for i, fn in enumerate(all_funcs, 1):
        print(f'   {i:3}. {fn}')
    total += len(all_funcs)

print(f'\n{"="*60}')
print(f'ВСЕГО: {total} функций')
print("="*60)
