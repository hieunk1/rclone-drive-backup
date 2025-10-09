#!/bin/bash
# scripts/generate_media_from_outputs.sh
# Usage: ./generate_media_from_outputs.sh <output_dir> <eleven_api_key> <bg_image>

OUTPUT_DIR=$1
ELEVEN_API_KEY=$2
BG_IMAGE=$3

echo "=== Generate media from outputs ==="
echo "Output dir: $OUTPUT_DIR"
echo "ELEVEN_API_KEY: (hidden)"
echo "Background image: $BG_IMAGE"

# Ví dụ: giả lập tạo file audio từ output text
for txt in "$OUTPUT_DIR"/*.txt; do
  base=$(basename "$txt" .txt)
  out_audio="$OUTPUT_DIR/${base}.mp3"
  echo "Fake audio for $txt" | ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 2 -q:a 9 -acodec libmp3lame "$out_audio"
  echo "Created $out_audio"
done
