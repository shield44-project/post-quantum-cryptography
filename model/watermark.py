import torch
import hashlib


def generate_watermark(text):

    digest = hashlib.sha256(
        text.encode()
    ).digest()

    bits = []

    for byte in digest:

        for i in range(8):

            bits.append(
                (byte >> i) & 1
            )

    return bits


def embed_watermark(
    model,
    watermark_text,
    strength=0.0001
):

    bits = generate_watermark(
        watermark_text
    )

    with torch.no_grad():

        parameters = []

        for param in model.parameters():

            if param.requires_grad:
                parameters.append(
                    param.view(-1)
                )

        all_parameters = torch.cat(
            parameters
        )

        for i, bit in enumerate(bits):

            value = all_parameters[i]

            if bit == 1:

                all_parameters[i] = (
                    torch.abs(value)
                    + strength
                )

            else:

                all_parameters[i] = (
                    -torch.abs(value)
                    - strength
                )

    return model


def detect_watermark(
    model,
    watermark_text
):

    expected_bits = generate_watermark(
        watermark_text
    )

    parameters = []

    for param in model.parameters():

        if param.requires_grad:
            parameters.append(
                param.view(-1)
            )

    all_parameters = torch.cat(
        parameters
    )

    detected_bits = []

    for i in range(
        len(expected_bits)
    ):

        value = all_parameters[i].item()

        detected_bits.append(
            1 if value > 0 else 0
        )

    matches = sum(
        a == b
        for a, b in zip(
            expected_bits,
            detected_bits
        )
    )

    accuracy = (
        matches /
        len(expected_bits)
    )

    return accuracy
