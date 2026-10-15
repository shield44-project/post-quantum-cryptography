import oqs
import time
import statistics


ALGORITHM = "ML-DSA-65"


def benchmark(runs=20):

    keygen_times = []
    sign_times = []
    verify_times = []

    message = (
        b"CIFAR-10 dataset provenance "
        b"manifest for experiment"
    )

    for _ in range(runs):

        signer = oqs.Signature(
            ALGORITHM
        )

        start = time.perf_counter()

        public_key = (
            signer.generate_keypair()
        )

        secret_key = (
            signer.export_secret_key()
        )

        end = time.perf_counter()

        keygen_times.append(
            end - start
        )

        signer = oqs.Signature(
            ALGORITHM,
            secret_key=secret_key
        )

        start = time.perf_counter()

        signature = signer.sign(
            message
        )

        end = time.perf_counter()

        sign_times.append(
            end - start
        )

        verifier = oqs.Signature(
            ALGORITHM
        )

        start = time.perf_counter()

        valid = verifier.verify(
            message,
            signature,
            public_key
        )

        end = time.perf_counter()

        verify_times.append(
            end - start
        )

    print("\nML-DSA-65 BENCHMARK")
    print("--------------------")

    print(
        "Average key generation:",
        statistics.mean(keygen_times)
    )

    print(
        "Average signing:",
        statistics.mean(sign_times)
    )

    print(
        "Average verification:",
        statistics.mean(verify_times)
    )

    print(
        "Public key size:",
        len(public_key)
    )

    print(
        "Secret key size:",
        len(secret_key)
    )

    print(
        "Signature size:",
        len(signature)
    )


if __name__ == "__main__":
    benchmark()

