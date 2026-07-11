import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Mock Lintai for testing")
    parser.add_argument("--version", action="store_true", help="Print version")
    parser.add_argument("command", nargs="?", help="Command (e.g. scan)")
    parser.add_argument("file", nargs="?", help="File to scan")
    parser.add_argument("--format", help="Output format")

    args, unknown = parser.parse_known_args()

    if args.version or "--version" in unknown:
        print("lintai v0.1.0")
        sys.exit(0)

    if args.command == "scan":
        # 파일 내용을 읽어 간단한 휴리스틱으로 위험 요소를 판단합니다 (모의).
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()

            # 위험 키워드가 있으면 차단 (단순화된 룰)
            danger_keywords = ["RM -RF", "SUDO", "PASSWORDS="]
            findings = []
            for kw in danger_keywords:
                if kw.lower() in content.lower():
                    findings.append({"rule": "SEC001", "message": f"Dangerous keyword found: {kw}"})

            if findings:
                if args.format == "json":
                    print(json.dumps({"findings": findings}))
                sys.exit(1)
            else:
                if args.format == "json":
                    print(json.dumps({"status": "clean", "findings": []}))
                sys.exit(0)

        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(2)


if __name__ == "__main__":
    main()
