/* Ed25519 (RFC 8032) + SHA-512 em JavaScript puro (BigInt), sem dependências e sem rede. */
var WMSTEd = (function () {
  var P = (1n << 255n) - 19n, L = (1n << 252n) + 27742317777372353535851937790883648493n;
  function mod(a, m) { m = m || P; var r = a % m; return r < 0n ? r + m : r; }
  function pw(b, e, m) { m = m || P; var r = 1n; b = mod(b, m); while (e > 0n) { if (e & 1n) r = r * b % m; b = b * b % m; e >>= 1n; } return r; }
  function inv(a) { return pw(a, P - 2n); }
  var D = mod(-121665n * inv(121666n)), I = pw(2n, (P - 1n) / 4n);
  function xr(y) { var xx = mod((y * y - 1n) * inv(D * y * y + 1n)); var x = pw(xx, (P + 3n) / 8n); if (mod(x * x - xx)) x = mod(x * I); if (x & 1n) x = P - x; return x; }
  var By = mod(4n * inv(5n)), Bx = xr(By), B = [Bx, By, 1n, mod(Bx * By)];
  function add(p, q) {
    var A = mod((p[1] - p[0]) * (q[1] - q[0])), b = mod((p[1] + p[0]) * (q[1] + q[0])), C = mod(2n * p[3] * q[3] * D), d = mod(2n * p[2] * q[2]);
    var E = b - A, F = d - C, G = d + C, H = b + A; return [mod(E * F), mod(G * H), mod(F * G), mod(E * H)];
  }
  function mul(s, p) { var q = [0n, 1n, 1n, 0n]; while (s > 0n) { if (s & 1n) q = add(q, p); p = add(p, p); s >>= 1n; } return q; }
  function le2n(b) { var n = 0n; for (var i = b.length - 1; i >= 0; i--) n = (n << 8n) | BigInt(b[i]); return n; }
  function n2le(n, len) { var o = new Uint8Array(len); for (var i = 0; i < len; i++) { o[i] = Number(n & 255n); n >>= 8n; } return o; }
  function enc(p) { var zi = inv(p[2]), x = mod(p[0] * zi), y = mod(p[1] * zi); return n2le(y | ((x & 1n) << 255n), 32); }
  // SHA-512
  var K = ["428a2f98d728ae22","7137449123ef65cd","b5c0fbcfec4d3b2f","e9b5dba58189dbbc","3956c25bf348b538","59f111f1b605d019","923f82a4af194f9b","ab1c5ed5da6d8118","d807aa98a3030242","12835b0145706fbe","243185be4ee4b28c","550c7dc3d5ffb4e2","72be5d74f27b896f","80deb1fe3b1696b1","9bdc06a725c71235","c19bf174cf692694","e49b69c19ef14ad2","efbe4786384f25e3","0fc19dc68b8cd5b5","240ca1cc77ac9c65","2de92c6f592b0275","4a7484aa6ea6e483","5cb0a9dcbd41fbd4","76f988da831153b5","983e5152ee66dfab","a831c66d2db43210","b00327c898fb213f","bf597fc7beef0ee4","c6e00bf33da88fc2","d5a79147930aa725","06ca6351e003826f","142929670a0e6e70","27b70a8546d22ffc","2e1b21385c26c926","4d2c6dfc5ac42aed","53380d139d95b3df","650a73548baf63de","766a0abb3c77b2a8","81c2c92e47edaee6","92722c851482353b","a2bfe8a14cf10364","a81a664bbc423001","c24b8b70d0f89791","c76c51a30654be30","d192e819d6ef5218","d69906245565a910","f40e35855771202a","106aa07032bbd1b8","19a4c116b8d2d0c8","1e376c085141ab53","2748774cdf8eeb99","34b0bcb5e19b48a8","391c0cb3c5c95a63","4ed8aa4ae3418acb","5b9cca4f7763e373","682e6ff3d6b2b8a3","748f82ee5defb2fc","78a5636f43172f60","84c87814a1f0ab72","8cc702081a6439ec","90befffa23631e28","a4506cebde82bde9","bef9a3f7b2c67915","c67178f2e372532b","ca273eceea26619c","d186b8c721c0c207","eada7dd6cde0eb1e","f57d4f7fee6ed178","06f067aa72176fba","0a637dc5a2c898a6","113f9804bef90dae","1b710b35131c471b","28db77f523047d84","32caab7b40c72493","3c9ebe0a15c9bebc","431d67c49c100d4c","4cc5d4becb3e42b6","597f299cfc657e2a","5fcb6fab3ad6faec","6c44198c4a475817"].map(function (h) { return BigInt("0x" + h); });
  var M64 = (1n << 64n) - 1n;
  function rotr(x, n) { return ((x >> n) | (x << (64n - n))) & M64; }
  function sha512(msg) {
    var len = msg.length, padLen = ((len + 17 + 127) >> 7) << 7, b = new Uint8Array(padLen);
    b.set(msg); b[len] = 0x80; var bits = BigInt(len) * 8n;
    for (var i = 0; i < 16; i++) b[padLen - 1 - i] = Number((bits >> BigInt(8 * i)) & 255n);
    var h = ["6a09e667f3bcc908","bb67ae8584caa73b","3c6ef372fe94f82b","a54ff53a5f1d36f1","510e527fade682d1","9b05688c2b3e6c1f","1f83d9abfb41bd6b","5be0cd19137e2179"].map(function (x) { return BigInt("0x" + x); });
    var w = new Array(80);
    for (var o = 0; o < padLen; o += 128) {
      for (var t = 0; t < 16; t++) { var v = 0n; for (var j = 0; j < 8; j++) v = (v << 8n) | BigInt(b[o + t * 8 + j]); w[t] = v; }
      for (t = 16; t < 80; t++) {
        var s0 = rotr(w[t - 15], 1n) ^ rotr(w[t - 15], 8n) ^ (w[t - 15] >> 7n), s1 = rotr(w[t - 2], 19n) ^ rotr(w[t - 2], 61n) ^ (w[t - 2] >> 6n);
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) & M64;
      }
      var a = h[0], bb = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
      for (t = 0; t < 80; t++) {
        var S1 = rotr(e, 14n) ^ rotr(e, 18n) ^ rotr(e, 41n), ch = (e & f) ^ (~e & M64 & g), t1 = (hh + S1 + ch + K[t] + w[t]) & M64;
        var S0 = rotr(a, 28n) ^ rotr(a, 34n) ^ rotr(a, 39n), mj = (a & bb) ^ (a & c) ^ (bb & c), t2 = (S0 + mj) & M64;
        hh = g; g = f; f = e; e = (d + t1) & M64; d = c; c = bb; bb = a; a = (t1 + t2) & M64;
      }
      h = [h[0] + a, h[1] + bb, h[2] + c, h[3] + d, h[4] + e, h[5] + f, h[6] + g, h[7] + hh].map(function (x) { return x & M64; });
    }
    var out = new Uint8Array(64);
    for (i = 0; i < 8; i++) for (j = 0; j < 8; j++) out[i * 8 + j] = Number((h[i] >> BigInt(56 - 8 * j)) & 255n);
    return out;
  }
  function cat() { var n = 0, i; for (i = 0; i < arguments.length; i++) n += arguments[i].length; var o = new Uint8Array(n), k = 0; for (i = 0; i < arguments.length; i++) { o.set(arguments[i], k); k += arguments[i].length; } return o; }
  function expand(seed) { var h = sha512(seed), a = le2n(h.slice(0, 32)); a &= (1n << 254n) - 8n; a |= 1n << 254n; return [a, h.slice(32)]; }
  function publica(seed) { return enc(mul(expand(seed)[0], B)); }
  function assinar(seed, msg) {
    var e = expand(seed), a = e[0], A = enc(mul(a, B));
    var r = le2n(sha512(cat(e[1], msg))) % L, R = enc(mul(r, B));
    var s = (r + le2n(sha512(cat(R, A, msg))) % L * a) % L;
    return cat(R, n2le(s, 32));
  }
  return { publica: publica, assinar: assinar, sha512: sha512, cat: cat };
})();
if (typeof module !== "undefined") module.exports = WMSTEd;
