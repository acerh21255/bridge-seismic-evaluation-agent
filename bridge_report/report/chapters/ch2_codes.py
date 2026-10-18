"""Chapter 2: referenced codes."""


def build(b):
    b.h(1, '参考规范')
    codes = b.get('codes', [], '参考规范清单')
    if not codes:
        b.p('（参考规范清单待第三步提供）')
    for n, code in enumerate(codes, start=1):
        b.p(f"（{n}）{code}{'。' if n == len(codes) else '；'}")
