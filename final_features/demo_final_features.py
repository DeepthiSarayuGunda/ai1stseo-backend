"""Upgraded demo runner for all Dev 4 final features."""
import sys


def _sep(title):
    print()
    print("=" * 64)
    print("  " + title)
    print("=" * 64)


def _section(n, title):
    print()
    print("  [" + str(n) + "] " + title)
    print("  " + "-" * 58)


def run_final_features_demo(topic="AI-powered SEO for small businesses"):
    """Run all final feature generators and print results."""
    _sep("FINAL FEATURES DEMO: " + topic)

    # 1. Full Content Generator
    _section(1, "CONTENT GENERATOR (ready-to-post)")
    from final_features.content_generator import generate_full_content
    content_eng = generate_full_content(topic, style="engaging")
    content_pro = generate_full_content(topic, style="professional")

    print("    --- Engaging Style ---")
    if content_eng.get("success"):
        print("    Title: " + content_eng["title"])
        print("    Hashtags: " + " ".join(content_eng["hashtags"][:5]))
        print("    Caption:")
        for line in content_eng["caption"].splitlines():
            print("      " + line)
    else:
        print("    ERROR: " + str(content_eng.get("error")))

    print()
    print("    --- Professional Style ---")
    if content_pro.get("success"):
        print("    Title: " + content_pro["title"])
        print("    Hashtags: " + " ".join(content_pro["hashtags"][:5]))
        print("    Caption:")
        for line in content_pro["caption"].splitlines():
            print("      " + line)
    else:
        print("    ERROR: " + str(content_pro.get("error")))

    # 2. Templates
    _section(2, "TEMPLATES")
    from final_features.template_generator import generate_template
    tpl_pro = generate_template(topic, style="professional")
    tpl_eng = generate_template(topic, style="engaging")
    print("    Professional: " + (tpl_pro.get("hook", "")[:60] + "..." if tpl_pro.get("success") else "FAIL"))
    print("    Engaging:     " + (tpl_eng.get("hook", "")[:60] + "..." if tpl_eng.get("success") else "FAIL"))

    # 3. Images (AI / Pexels / Placeholder)
    _section(3, "IMAGE GENERATOR")
    from final_features.image_generator import generate_image
    img = generate_image(topic)
    if img.get("success"):
        print("    Source: " + img["source"].upper())
        images = img.get("images", [])
        for i, im in enumerate(images):
            url = im.get("url", "")
            desc = im.get("description", "")
            local = im.get("local_path", "")
            line = "    " + str(i + 1) + ". " + url[:70]
            if desc:
                line += " | " + desc[:40]
            print(line)
            if local:
                print("       Saved: " + local)
    else:
        print("    ERROR: " + str(img.get("error")))

    # 4. Video (real or simulated)
    _section(4, "VIDEO GENERATOR")
    from final_features.video_generator import generate_video
    vid = generate_video(topic)
    if vid.get("success"):
        print("    Duration: " + str(vid["duration_seconds"]) + "s | Words: " + str(vid["word_count"]))
        media = vid.get("media_generated", False)
        print("    Media:    " + ("REAL FILES GENERATED" if media else "Simulated (install gTTS + moviepy for real output)"))
        if vid.get("audio_path"):
            print("    Audio:    " + vid["audio_path"])
        if vid.get("video_path"):
            print("    Video:    " + vid["video_path"])
        else:
            print("    URL:      " + vid["video_url"])
        print("    Intro:    " + vid.get("intro", ""))
        scenes = vid.get("scenes", [])
        for s in scenes:
            print("    Scene " + str(s["scene"]) + ":  " + s["title"] + " (" + str(s["duration_sec"]) + "s)")
        print("    Outro:    " + vid.get("outro", ""))
    else:
        print("    ERROR: " + str(vid.get("error")))

    # 5. Outreach Email
    _section(5, "OUTREACH EMAIL")
    from final_features.outreach_email import generate_outreach_email
    email = generate_outreach_email("Sarah Johnson", "GrowthCo Marketing")
    if email.get("success"):
        print("    To:      " + email["to_name"] + " at " + email["to_organization"])
        print("    Subject: " + email["subject"])
        print("    Body:")
        for line in email["body"].splitlines():
            print("      " + line)
    else:
        print("    ERROR: " + str(email.get("error")))

    # Summary
    _sep("DEMO COMPLETE")
    results = [
        ("Content generator (engaging)", content_eng.get("success")),
        ("Content generator (professional)", content_pro.get("success")),
        ("Template (professional)", tpl_pro.get("success")),
        ("Template (engaging)", tpl_eng.get("success")),
        ("Image generator [" + img.get("source", "?").upper() + "]", img.get("success")),
        ("Video generator [" + ("REAL" if vid.get("media_generated") else "SIM") + "]", vid.get("success")),
        ("Outreach email", email.get("success")),
    ]
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print("    [" + status + "] " + name)
    passed = sum(1 for _, ok in results if ok)
    print()
    print("    " + str(passed) + "/" + str(len(results)) + " features working")
    print()


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "AI-powered SEO for small businesses"
    run_final_features_demo(t)
