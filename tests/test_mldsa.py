import oqs

ALG = "ML-DSA-65"
print("ML-DSA-65 enabled:", ALG in oqs.get_enabled_sig_mechanisms())

message = b"hello"

with oqs.Signature(ALG) as signer:
    public_key = signer.generate_keypair()
    signature = signer.sign(message)

print("public key bytes:", len(public_key))
print("signature bytes:", len(signature))

with oqs.Signature(ALG) as verifier:
    print("correct message:", verifier.verify(message, signature, public_key))
    print("tampered message:", verifier.verify(b"hellp", signature, public_key))