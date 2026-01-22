from rate_limit import rate_limiter
user = rate_limiter.get_user(123)
fields = [f for f in dir(user) if not f.startswith('_')]
print('Поля UserState:')
for f in sorted(fields):
    print(f'  - {f}')
print(f'\nВсего: {len(fields)} полей')
