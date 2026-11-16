/* Montagem do serial do WMusic Steams (igual ao wmsteams/licenca.py). */
var WMSTSerial = (function () {
  var ALF = "0123456789ABCDEFGHJKMNPQRSTVWXYZ", CTX = new TextEncoder().encode("WMUSIC STEAMS 1");
  function b32(b) { var s = "", acc = 0, bits = 0; for (var i = 0; i < b.length; i++) { acc = ((acc << 8) | b[i]) & 0xFFFF; bits += 8; while (bits >= 5) { s += ALF[(acc >> (bits - 5)) & 31]; bits -= 5; } } if (bits) s += ALF[(acc << (5 - bits)) & 31]; return s; }
  function deB32(s) { var o = [], acc = 0, bits = 0; for (var i = 0; i < s.length; i++) { acc = ((acc << 5) | ALF.indexOf(s[i])) & 0xFFFF; bits += 5; if (bits >= 8) { o.push((acc >> (bits - 8)) & 255); bits -= 8; } } return new Uint8Array(o); }
  function limpar(t) { t = String(t).toUpperCase().replace(/O/g, "0").replace(/[IL]/g, "1").replace(/U/g, "V"); var r = ""; for (var i = 0; i < t.length; i++) if (ALF.indexOf(t[i]) >= 0) r += t[i]; return r; }
  function codigo(c) { var x = limpar(c); if (x.length !== 8) throw new Error("O código do computador tem 8 letras e números (ex.: AB12-CD34)."); return deB32(x); }
  function dias(data) { return Math.round((Date.UTC(data.getFullYear(), data.getMonth(), data.getDate()) - Date.UTC(2026, 0, 1)) / 864e5); }
  function montar(seed, nome, tipo, cod, validade, identHex, hoje) {
    hoje = hoje || new Date();
    var maq = cod ? codigo(cod) : new Uint8Array(5);
    if (tipo === 1 && !cod) throw new Error("Serial de venda precisa do código do computador do cliente.");
    if (tipo === 2 && !validade) throw new Error("Serial de beta precisa de data de validade.");
    var nb = new TextEncoder().encode(String(nome).trim()); if (nb.length > 48) { nb = nb.slice(0, 48); while (nb.length && (nb[nb.length - 1] & 0xC0) === 0x80) nb = nb.slice(0, -1); if (nb.length && nb[nb.length - 1] >= 0xC0) nb = nb.slice(0, -1); }
    var id = new Uint8Array(4);
    if (identHex) for (var i = 0; i < 4; i++) id[i] = parseInt(identHex.substr(i * 2, 2), 16); else crypto.getRandomValues(id);
    var e = dias(hoje), v = validade ? dias(validade) : 0;
    var head = new Uint8Array([1, tipo, id[0], id[1], id[2], id[3], e >> 8, e & 255, v >> 8, v & 255, maq[0], maq[1], maq[2], maq[3], maq[4], nb.length]);
    var payload = WMSTEd.cat(head, nb), sig = WMSTEd.assinar(seed, WMSTEd.cat(CTX, payload));
    var s = b32(WMSTEd.cat(payload, sig)), g = [];
    for (i = 0; i < s.length; i += 5) g.push(s.slice(i, i + 5));
    return { serial: "WMST-" + g.join("-"), id: Array.prototype.map.call(id, function (x) { return (x < 16 ? "0" : "") + x.toString(16); }).join("").toUpperCase() };
  }
  return { montar: montar, codigo: codigo, limpar: limpar, b32: b32 };
})();
if (typeof module !== "undefined") module.exports = WMSTSerial;
