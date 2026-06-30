#!/usr/bin/env python3
"""
Audio Converter Utility
Handles exporting PCM lists or converting existing WAV recordings into high-quality MP3 or OGG.
Can be imported as a library or run as a standalone CLI.
"""

import os
import sys
import struct
import shutil
import argparse
from pydub import AudioSegment

def is_ffmpeg_available() -> bool:
    """Checks if ffmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None

def print_ffmpeg_instructions():
    """Prints friendly instruction on how to install ffmpeg on macOS."""
    print("=" * 70, file=sys.stderr)
    print("[WARNING] ffmpeg is not installed or not found in your PATH.", file=sys.stderr)
    print("pydub requires ffmpeg to decode/encode MP3 or OGG formats.", file=sys.stderr)
    print("\nTo resolve this on macOS, run the following command in your terminal:", file=sys.stderr)
    print("    brew install ffmpeg", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

def save_pcm_as_mp3_ogg(
    inbound_pcm: list[int],
    outbound_pcm: list[int],
    output_path: str,
    fmt: str = "mp3",
    sample_rate: int = 8000
) -> bool:
    """
    Stitches inbound and outbound PCM sample lists into a stereo audio file
    and exports it as MP3 or OGG.
    
    Channel 1 (Left): Inbound (the clinic receptionist/agent)
    Channel 2 (Right): Outbound (our patient bot)
    
    Returns:
        bool: True if successful, False otherwise.
    """
    if not is_ffmpeg_available():
        print_ffmpeg_instructions()
        return False
        
    try:
        # Pad the shorter stream with silence (zeros)
        max_len = max(len(inbound_pcm), len(outbound_pcm))
        
        # Avoid mutate original lists
        inbound_padded = inbound_pcm + [0] * (max_len - len(inbound_pcm))
        outbound_padded = outbound_pcm + [0] * (max_len - len(outbound_pcm))
        
        # Pack lists of integers into binary little-endian 16-bit format
        inbound_bytes = struct.pack(f"<{max_len}h", *inbound_padded)
        outbound_bytes = struct.pack(f"<{max_len}h", *outbound_padded)
        
        # Create Mono Audio Segments (16-bit, 8kHz, 1 channel)
        in_segment = AudioSegment(
            data=inbound_bytes,
            sample_width=2,
            frame_rate=sample_rate,
            channels=1
        )
        
        out_segment = AudioSegment(
            data=outbound_bytes,
            sample_width=2,
            frame_rate=sample_rate,
            channels=1
        )
        
        # Merge into Stereo (Left = Agent, Right = Patient)
        stereo_segment = AudioSegment.from_mono_audiosegments(in_segment, out_segment)
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Export high-quality MP3/OGG (128kbps is excellent for voice)
        bitrate = "128k"
        stereo_segment.export(output_path, format=fmt, bitrate=bitrate)
        print(f"[SUCCESS] Exported high-quality {fmt.upper()} to: {output_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to save PCM as {fmt.upper()}: {e}", file=sys.stderr)
        return False

def convert_wav_file(wav_path: str, output_path: str, fmt: str = "mp3") -> bool:
    """
    Converts an existing WAV file to MP3 or OGG.
    """
    if not is_ffmpeg_available():
        print_ffmpeg_instructions()
        return False
        
    if not os.path.exists(wav_path):
        print(f"[ERROR] WAV file not found: {wav_path}", file=sys.stderr)
        return False
        
    try:
        # Load WAV
        audio = AudioSegment.from_wav(wav_path)
        
        # Ensure output folder exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Export
        audio.export(output_path, format=fmt, bitrate="128k")
        print(f"[SUCCESS] Converted {wav_path} -> {output_path} ({fmt.upper()})")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to convert {wav_path}: {e}", file=sys.stderr)
        return False

def batch_convert_directory(input_dir: str, output_dir: str, fmt: str = "mp3"):
    """
    Batch converts all WAV files in the input directory to MP3 or OGG.
    """
    if not os.path.exists(input_dir):
        print(f"[ERROR] Input directory not found: {input_dir}", file=sys.stderr)
        return
        
    files = [f for f in os.listdir(input_dir) if f.endswith(".wav")]
    if not files:
        print(f"No WAV files found in: {input_dir}")
        return
        
    print(f"Found {len(files)} WAV files in {input_dir}. Converting to {fmt.upper()}...")
    success_count = 0
    for file in files:
        wav_path = os.path.join(input_dir, file)
        out_filename = os.path.splitext(file)[0] + f".{fmt}"
        out_path = os.path.join(output_dir, out_filename)
        if convert_wav_file(wav_path, out_path, fmt):
            success_count += 1
            
    print(f"Batch conversion complete: {success_count}/{len(files)} files converted successfully.")

def main():
    parser = argparse.ArgumentParser(
        description="Convert Call WAV recordings or directories of WAVs into MP3/OGG format."
    )
    parser.add_argument(
        "path",
        help="Path to a WAV file or a directory containing WAV files."
    )
    parser.add_argument(
        "-f", "--format",
        choices=["mp3", "ogg"],
        default="mp3",
        help="Target audio format (default: mp3)."
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path or directory (optional)."
    )
    
    args = parser.parse_args()
    
    # Check ffmpeg first
    if not is_ffmpeg_available():
        print_ffmpeg_instructions()
        sys.exit(1)
        
    path = args.path
    fmt = args.format
    output = args.output
    
    if os.path.isdir(path):
        out_dir = output if output else path
        batch_convert_directory(path, out_dir, fmt)
    elif os.path.isfile(path):
        if not path.endswith(".wav"):
            print(f"[WARNING] Input file '{path}' does not end in '.wav'. Trying to convert anyway.")
        
        if output:
            out_path = output
        else:
            out_path = os.path.splitext(path)[0] + f".{fmt}"
            
        convert_wav_file(path, out_path, fmt)
    else:
        print(f"[ERROR] Path not found: {path}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
