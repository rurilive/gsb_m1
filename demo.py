"""b85x 联调自检：两套编解码的 roundtrip 和分块一致性。"""

from b85x import Base32Decoder, Base32Encoder, Base85Decoder, Base85Encoder

payload = b"gateway-frame-0042"

print("=== Base85 一次性 ===")
enc = Base85Encoder()
text = enc.encode_feed(payload) + enc.finish()
print("encoded:", text)
dec = Base85Decoder()
print("roundtrip ok:", dec.decode_feed(text) + dec.finish() == payload)

print("\n=== Base85 分块 8+8+2 ===")
chunks = [payload[i:i + 8] for i in range(0, len(payload), 8)]
enc = Base85Encoder()
parts = [enc.encode_feed(c) for c in chunks]
parts.append(enc.finish())
text2 = "".join(parts)
dec = Base85Decoder()
print("chunk sizes:", [len(c) for c in chunks])
print("same as one-shot:", text2 == text,
      "roundtrip ok:", dec.decode_feed(text2) + dec.finish() == payload)

print("\n=== Base32 ===")
payload32 = b"v2-ok-77"
enc = Base32Encoder()
text32 = enc.encode_feed(payload32) + enc.finish()
print("encoded:", text32)
dec = Base32Decoder()
print("roundtrip ok:", dec.decode_feed(text32) + dec.finish() == payload32)
