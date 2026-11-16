"""Ed25519 (RFC 8032) em Python puro, sem dependências: o app só confere a
assinatura do serial; o gerador do Heitor também assina com este arquivo."""
import hashlib

p = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
d = -121665 * pow(121666, p - 2, p) % p
I = pow(2, (p - 1) // 4, p)


def _xr(y):
    xx = (y * y - 1) * pow(d * y * y + 1, p - 2, p) % p
    x = pow(xx, (p + 3) // 8, p)
    if (x * x - xx) % p:
        x = x * I % p
    if (x * x - xx) % p:
        return None
    if x % 2:
        x = p - x
    return x


_By = 4 * pow(5, p - 2, p) % p
B = (_xr(_By), _By, 1, _xr(_By) * _By % p)


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % p
    Bb = (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C = 2 * P[3] * Q[3] * d % p
    D = 2 * P[2] * Q[2] % p
    E, F, G, H = Bb - A, D - C, D + C, Bb + A
    return (E * F % p, G * H % p, F * G % p, E * H % p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _enc(P):
    zi = pow(P[2], p - 2, p)
    x = P[0] * zi % p
    y = P[1] * zi % p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _dec(b):
    if len(b) != 32:
        return None
    n = int.from_bytes(b, "little")
    y = n & ((1 << 255) - 1)
    if y >= p:
        return None
    x = _xr(y)
    if x is None:
        return None
    if (x & 1) != (n >> 255):
        if x == 0:
            return None
        x = p - x
    return (x, y, 1, x * y % p)


def _h(m):
    return int.from_bytes(hashlib.sha512(m).digest(), "little")


def _expand(seed):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def publica(seed: bytes) -> bytes:
    a, _ = _expand(seed)
    return _enc(_mul(a, B))


def assinar(seed: bytes, msg: bytes) -> bytes:
    a, pre = _expand(seed)
    A = _enc(_mul(a, B))
    r = _h(pre + msg) % L
    R = _enc(_mul(r, B))
    s = (r + _h(R + A + msg) * a) % L
    return R + int.to_bytes(s, 32, "little")


def conferir(pub: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        if len(sig) != 64 or len(pub) != 32:
            return False
        A = _dec(pub)
        R = _dec(sig[:32])
        s = int.from_bytes(sig[32:], "little")
        if A is None or R is None or s >= L:
            return False
        k = _h(sig[:32] + pub + msg) % L
        return _enc(_mul(s, B)) == _enc(_add(R, _mul(k, A)))
    except Exception:
        return False
