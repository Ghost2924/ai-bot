import os
import struct
import wave

# Precomputed G.711 mu-law to 16-bit linear PCM lookup table
# This covers all 256 possible byte values (0x00 to 0xFF)
ULAW_TABLE = [
    -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
    -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
    -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
    -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
    -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
    -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
    -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
    -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
    -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
    -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
    -876, -844, -812, -780, -748, -716, -684, -652,
    -620, -588, -556, -524, -492, -460, -428, -396,
    -372, -356, -340, -324, -308, -292, -276, -260,
    -244, -228, -212, -196, -180, -164, -148, -132,
    -120, -112, -104, -96, -88, -80, -72, -64,
    -56, -48, -40, -32, -24, -16, -8, 0,
    32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
    23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
    15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
    11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
    7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
    5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
    3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
    2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
    1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
    1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
    876, 844, 812, 780, 748, 716, 684, 652,
    620, 588, 556, 524, 492, 460, 428, 396,
    372, 356, 340, 324, 308, 292, 276, 260,
    244, 228, 212, 196, 180, 164, 148, 132,
    120, 112, 104, 96, 88, 80, 72, 64,
    56, 48, 40, 32, 24, 16, 8, 0
]

def decode_ulaw_bytes(data: bytes) -> list[int]:
    """Decodes G.711 mu-law bytes into a list of 16-bit PCM integer samples."""
    return [ULAW_TABLE[b] for b in data]

def save_wav_stereo(filename: str, inbound_pcm: list[int], outbound_pcm: list[int], sample_rate: int = 8000):
    """
    Saves inbound and outbound PCM sample lists into a stereo WAV file.
    Channel 1 (Left): Inbound (the clinic receptionist/called party)
    Channel 2 (Right): Outbound (our patient bot)
    """
    # Find the maximum length and pad the shorter stream with zeros (silence)
    max_len = max(len(inbound_pcm), len(outbound_pcm))
    
    if len(inbound_pcm) < max_len:
        inbound_pcm.extend([0] * (max_len - len(inbound_pcm)))
    if len(outbound_pcm) < max_len:
        outbound_pcm.extend([0] * (max_len - len(outbound_pcm)))
        
    # Interleave the samples: L0, R0, L1, R1, L2, R2 ...
    stereo_samples = []
    for i in range(max_len):
        stereo_samples.append(inbound_pcm[i])
        stereo_samples.append(outbound_pcm[i])
        
    # Ensure directories exist
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Write to WAV
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(2)        # Stereo
        wav_file.setsampwidth(2)        # 2 bytes per sample (16-bit)
        wav_file.setframerate(sample_rate)
        
        # Pack list of integers into binary little-endian short/16-bit format
        packed_data = struct.pack(f"<{len(stereo_samples)}h", *stereo_samples)
        wav_file.writeframes(packed_data)

def ensure_directories():
    """Ensure that the transcripts and recordings folders exist."""
    os.makedirs("recordings", exist_ok=True)
    os.makedirs("transcripts", exist_ok=True)
