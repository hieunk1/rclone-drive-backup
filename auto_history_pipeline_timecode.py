#!/usr/bin/env python3
"""
auto_history_pipeline_timecode.py (updated)

Now generates 3 script variants per topic using 3 optimized prompts:
  - long       : in-depth narrative (300-500 words)
  - from_sum   : rewrite Wikipedia summary into engaging narrative (300-400 words)
  - short      : short script for Shorts/TikTok (100-150 words) and split into timecodes (1-minute layout)

Outputs per topic in out_folder:
  - script_{topic}.txt   (human readable: summary + all scripts + segments)
  - script_{topic}.json  (machine friendly: summary, scripts, segments metadata)

Usage example:
  python auto_history_pipeline_timecode.py --topics "Đế chế La Mã,Napoleon" --lang vi --out_folder ./outputs

Environment variables (optional):
  OPENAI_API_KEY : if set, OpenAI is used to generate scripts; otherwise falls back to local formatter.
"""
import os
import argparse
import json
import sys

# Ensure stdout/stderr use UTF-8 so printing unicode to Windows console won't crash
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Optional imports
try:
    import wikipedia
    WIKI_AVAILABLE = True
except Exception:
    WIKI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

# -------------------- Prompt templates --------------------
PROMPT_LONG = {
    "vi": """Bạn là một nhà biên soạn nội dung lịch sử. Hãy viết một kịch bản tường thuật dài 300–500 từ về chủ đề: "{TOPIC}".
Yêu cầu:
- Mở đầu gây tò mò, có câu hook hấp dẫn.
- Trình bày mạch lạc theo thời gian, có cao trào.
- Dùng ngôn từ dễ hiểu, phù hợp video YouTube (độ dài ~5-8 phút khi đọc chậm).
- Kết thúc có tính gợi mở để người xem muốn tìm hiểu thêm.
Ngôn ngữ: Tiếng Việt.
Trả về plain text.""",
    "en": """You are a historical content writer. Write a 300–500 word narrative script about: "{TOPIC}".
Requirements:
- Start with a compelling hook.
- Present chronologically with a climax.
- Use clear language suitable for a YouTube narration.
- End with a thought-provoking closing inviting further exploration.
Return plain text."""
}

PROMPT_FROM_SUMMARY = {
    "vi": """Bạn nhận được một đoạn tóm tắt Wikipedia sau:

"{SUMMARY}"

Hãy chuyển nội dung này thành một kịch bản kể chuyện lịch sử (300–400 từ) theo phong cách gần gũi, như một người dẫn chuyện trên video.
- Giữ tính chính xác nhưng giảm khô khan.
- Thêm chi tiết thú vị hoặc ngữ cảnh lịch sử nếu thích hợp.
- Giữ giọng văn hấp dẫn, phù hợp khán giả phổ thông.
Ngôn ngữ: Tiếng Việt.
Trả về plain text.""",
    "en": """You receive the following Wikipedia summary:

"{SUMMARY}"

Convert this into a 300–400 word historical storytelling script in a friendly, narrator style suitable for a video.
- Keep accuracy but reduce dryness.
- Add interesting details or context where relevant.
- Maintain an engaging tone for a general audience.
Language: English.
Return plain text."""
}

PROMPT_SHORT = {
    "vi": """Bạn là storyteller. Viết kịch bản ngắn (100–150 từ) về "{TOPIC}" để dùng cho video Shorts/TikTok (khoảng 1 phút).
Yêu cầu:
- Bắt đầu bằng 1 câu hỏi hoặc 1 sự thật gây tò mò.
- Trình bày nhanh, rõ ràng: 3 ý ngắn (mỗi ý 1 câu).
- Kết thúc 1 câu CTA (kêu gọi like/subscribe hoặc "xem tiếp").
Ngôn ngữ: Tiếng Việt.
Trả về plain text.""",
    "en": """You are a storyteller. Write a short 100–150 word script about "{TOPIC}" for a Shorts/TikTok (~1 minute).
Requirements:
- Start with a question or striking fact.
- Present 3 concise points (one sentence each).
- End with a CTA (subscribe/like or "learn more").
Language: English.
Return plain text."""
}

# -------------------- Helpers --------------------
def fetch_wikipedia_summary(topic: str, lang: str = "vi", sentences: int = 6):
    if not WIKI_AVAILABLE:
        raise RuntimeError("Package wikipedia không có. Cài: pip install wikipedia")
    wikipedia.set_lang(lang)
    summary = wikipedia.summary(topic, sentences=sentences)
    page = wikipedia.page(topic)
    return summary, page.content[:5000]

def call_openai(prompt: str, model: str = "gpt-4o-mini"):
    if not OPENAI_AVAILABLE:
        raise RuntimeError("openai package not installed. pip install openai")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set.")
    openai.api_key = key
    resp = openai.ChatCompletion.create(
        model=model,
        messages=[{"role":"user","content":prompt}],
        max_tokens=800,
        temperature=0.7
    )
    return resp['choices'][0]['message']['content'].strip()

def local_fallback_formatter_long(topic: str, summary: str, lang: str = "vi"):
    # Create a longer narrative by expanding summary sentences naively
    sents = [s.strip() for s in summary.replace("\n"," ").split('.') if s.strip()]
    intro = sents[0] if sents else f"{topic} là một chủ đề lịch sử thú vị."
    middle = " ".join(sents[1:6])
    closing = sents[6] if len(sents)>6 else ""
    if lang.startswith("vi"):
        return f"{intro}. {middle}. {closing}. Nếu bạn muốn tìm hiểu sâu hơn, hãy theo dõi kênh để xem các video tiếp theo."
    else:
        return f"{intro}. {middle}. {closing}. If you want to learn more, subscribe for future videos."

def local_fallback_formatter_fromsummary(summary: str, lang: str = "vi"):
    # Short rewrite: take first 4-6 sentences and make a compact narrative.
    sents = [s.strip() for s in summary.replace('\n',' ').split('.') if s.strip()]
    pts = sents[:6]
    if lang.startswith("vi"):
        return " ".join(pts) + " Nguồn: Wikipedia."
    else:
        return " ".join(pts) + " Sources: Wikipedia."

def local_fallback_formatter_short(topic: str, summary: str, lang: str = "vi"):
    # Create a short 3-point script from summary or topic
    sents = [s.strip() for s in summary.replace("\n"," ").split('.') if s.strip()]
    p1 = sents[0] if sents else f"{topic} có nhiều điều thú vị."
    p2 = sents[1] if len(sents)>1 else ""
    p3 = sents[2] if len(sents)>2 else ""
    if lang.startswith("vi"):
        hook = f"Bạn có biết về {topic}?"
        body = f"Ý 1: {p1}. Ý 2: {p2}. Ý 3: {p3}."
        cta = "Nếu bạn thích, hãy like và theo dõi."
        return f"{hook}\n\n{body}\n\n{cta}"
    else:
        hook = f"Did you know about {topic}?"
        body = f"Point 1: {p1}. Point 2: {p2}. Point 3: {p3}."
        cta = "Like and subscribe for more."
        return f"{hook}\n\n{body}\n\n{cta}"

# Timecode splitting for 1-minute short (uses short script)
def split_script_to_segments(script_text: str, lang: str = "vi"):
    parts = [p.strip() for p in script_text.split('\n') if p.strip()]
    hook = parts[0] if parts else ""
    middle = parts[1:-1] if len(parts)>2 else parts[1:]
    cta = parts[-1] if len(parts)>1 else ""
    points = []
    for p in middle:
        sents = [s.strip() for s in p.split('.') if s.strip()]
        for s in sents:
            if len(points) < 3:
                points.append(s)
    while len(points) < 3:
        points.append("")
    segs = []
    segs.append({'role':'hook','text':hook,'duration':8})
    for i in range(3):
        segs.append({'role':f'point{i+1}','text':points[i],'duration':15})
    segs.append({'role':'cta','text':cta,'duration':7})
    cur = 0
    for s in segs:
        s['start'] = cur
        s['end'] = cur + s['duration']
        cur = s['end']
    return segs

# Generate scripts using OpenAI if available, otherwise local fallbacks
def generate_three_scripts(topic: str, summary: str, lang: str = "vi"):
    lang_key = 'vi' if lang.startswith('vi') else 'en'
    scripts = {'long':None, 'from_summary':None, 'short':None}
    # Long narrative
    try:
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            prompt = PROMPT_LONG[lang_key].format(TOPIC=topic)
            scripts['long'] = call_openai(prompt)
        else:
            scripts['long'] = local_fallback_formatter_long(topic, summary, lang)
    except Exception as e:
        scripts['long'] = local_fallback_formatter_long(topic, summary, lang)
    # From summary
    try:
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            prompt = PROMPT_FROM_SUMMARY[lang_key].format(SUMMARY=summary)
            scripts['from_summary'] = call_openai(prompt)
        else:
            scripts['from_summary'] = local_fallback_formatter_fromsummary(summary, lang)
    except Exception as e:
        scripts['from_summary'] = local_fallback_formatter_fromsummary(summary, lang)
    # Short script
    try:
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            prompt = PROMPT_SHORT[lang_key].format(TOPIC=topic)
            scripts['short'] = call_openai(prompt)
        else:
            scripts['short'] = local_fallback_formatter_short(topic, summary, lang)
    except Exception as e:
        scripts['short'] = local_fallback_formatter_short(topic, summary, lang)
    return scripts

# Main processing per topic
def process_topic(topic: str, lang: str, out_folder: str, use_ai: bool):
    os.makedirs(out_folder, exist_ok=True)
    safe_name = topic.replace(' ','_').replace('/','_')
    txt_file = os.path.join(out_folder, f"script_{safe_name}.txt")
    json_file = os.path.join(out_folder, f"script_{safe_name}.json")
    # fetch summary
    try:
        summary, full = fetch_wikipedia_summary(topic, lang=lang, sentences=6)
    except Exception as e:
        # include exception message for debug in summary placeholder
        summary = f"[Không lấy được Wikipedia. Lý do: {str(e)}]"
        full = ""
    # generate scripts (AI or fallback will be chosen inside)
    scripts = generate_three_scripts(topic, summary, lang)
    # produce segments/timecodes from the SHORT script
    segments = split_script_to_segments(scripts['short'], lang=lang)
    # save text file (human readable)
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"# Topic: {topic}\n\n")
        f.write("---\n\n")
        f.write("# Summary (raw)\n\n")
        f.write(summary + "\n\n")
        f.write("---\n\n")
        f.write("# Scripts\n\n")
        f.write("## Long narrative\n\n")
        f.write(scripts['long'] + "\n\n")
        f.write("## From summary (story)\n\n")
        f.write(scripts['from_summary'] + "\n\n")
        f.write("## Short script (for Shorts)\n\n")
        f.write(scripts['short'] + "\n\n")
        f.write("---\n\n")
        f.write("# Segments (timecodes)\n\n")
        for s in segments:
            f.write(f"{s['role'].upper()} [{s['start']}s - {s['end']}s]: {s['text']}\n")
    # save json metadata
    meta = {
        'topic': topic,
        'lang': lang,
        'summary': summary,
        'scripts': scripts,
        'segments': segments
    }
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return txt_file, json_file

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--topics', required=True)
    parser.add_argument('--lang', default='vi')
    parser.add_argument('--out_folder', default='./outputs')
    parser.add_argument('--no_ai', action='store_true')
    args = parser.parse_args()
    topics = [t.strip() for t in args.topics.split(',') if t.strip()]
    for t in topics:
        print("Processing:", t)
        txt, js = process_topic(t, lang=args.lang, out_folder=args.out_folder, use_ai=not args.no_ai)
        print("Saved:", txt, js)
    print("Done.")

if __name__ == "__main__":
    main()
