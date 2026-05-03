#!/usr/bin/env python3
"""
Antigravity-K: MLX 설치 검증 & Metal GPU 벤치마크
=================================================
Mac 도착 후 실행: python verify_mlx.py
Windows에서는 "MLX 미설치" 안내만 표시됩니다.
"""

import sys
import time
import platform

# ─── Rich 콘솔 (설치되어 있으면 사용, 없으면 기본 print) ──────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    def header(text: str):
        console.print(Panel(text, style="bold cyan"))
    def success(text: str):
        console.print(f"  [green]✓[/green] {text}")
    def warn(text: str):
        console.print(f"  [yellow]![/yellow] {text}")
    def error(text: str):
        console.print(f"  [red]✗[/red] {text}")
    def info(text: str):
        console.print(f"  [blue]→[/blue] {text}")
except ImportError:
    def header(text: str):
        print(f"\n{'='*60}\n  {text}\n{'='*60}")
    def success(text: str):
        print(f"  ✓ {text}")
    def warn(text: str):
        print(f"  ! {text}")
    def error(text: str):
        print(f"  ✗ {text}")
    def info(text: str):
        print(f"  → {text}")


def check_platform() -> dict:
    """시스템 플랫폼 정보 수집"""
    header("1. 시스템 정보")

    result = {
        "os": platform.system(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "is_apple_silicon": False,
    }

    info(f"OS: {result['os']} {platform.release()}")
    info(f"Architecture: {result['arch']}")
    info(f"Python: {result['python']}")

    if result["os"] == "Darwin" and result["arch"] == "arm64":
        result["is_apple_silicon"] = True
        success("Apple Silicon 감지됨")

        # 메모리 정보 (macOS 전용)
        try:
            import subprocess
            mem_bytes = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"]
            ).strip())
            mem_gb = mem_bytes / (1024 ** 3)
            result["memory_gb"] = mem_gb
            info(f"Unified Memory: {mem_gb:.0f}GB")
        except Exception:
            pass
    elif result["os"] == "Windows":
        warn("Windows 환경입니다. MLX는 Mac 전용이므로 검증을 건너뜁니다.")
        warn("Mac 도착 후 다시 실행해 주세요.")
    else:
        warn(f"지원되지 않는 플랫폼: {result['os']} {result['arch']}")

    return result


def check_mlx_packages() -> dict:
    """MLX 관련 패키지 설치 상태 확인"""
    header("2. MLX 패키지 확인")

    packages = {}

    # MLX 코어
    try:
        import mlx.core as mx
        ver = mx.__version__
        packages["mlx"] = ver
        success(f"mlx: {ver}")
    except ImportError:
        packages["mlx"] = None
        error("mlx: 미설치")

    # MLX-LM (텍스트 모델 추론)
    try:
        import mlx_lm
        ver = getattr(mlx_lm, "__version__", "installed")
        packages["mlx-lm"] = ver
        success(f"mlx-lm: {ver}")
    except ImportError:
        packages["mlx-lm"] = None
        error("mlx-lm: 미설치")

    # MLX-VLM (비전 모델)
    try:
        import mlx_vlm
        ver = getattr(mlx_vlm, "__version__", "installed")
        packages["mlx-vlm"] = ver
        success(f"mlx-vlm: {ver}")
    except ImportError:
        packages["mlx-vlm"] = None
        error("mlx-vlm: 미설치")

    # ChromaDB (벡터 DB)
    try:
        import chromadb
        packages["chromadb"] = chromadb.__version__
        success(f"chromadb: {chromadb.__version__}")
    except ImportError:
        packages["chromadb"] = None
        warn("chromadb: 미설치 (Phase 3에서 필요)")

    # FastAPI
    try:
        import fastapi
        packages["fastapi"] = fastapi.__version__
        success(f"fastapi: {fastapi.__version__}")
    except ImportError:
        packages["fastapi"] = None
        warn("fastapi: 미설치 (Phase 2에서 필요)")

    return packages


def check_metal_gpu() -> dict:
    """Metal GPU 가속 확인"""
    header("3. Metal GPU 가속")

    result = {"available": False, "device": "unknown"}

    try:
        import mlx.core as mx

        device = mx.default_device()
        result["device"] = str(device)

        if "gpu" in str(device).lower():
            result["available"] = True
            success(f"Metal GPU 활성: {device}")
        else:
            warn(f"현재 디바이스: {device} (CPU 모드)")
            info("Metal GPU가 비활성 상태입니다.")
    except ImportError:
        warn("MLX 미설치로 Metal GPU 확인 불가")
    except Exception as e:
        error(f"디바이스 확인 실패: {e}")

    return result


def run_benchmark() -> dict:
    """MLX 행렬 연산 벤치마크 (CPU vs GPU)"""
    header("4. 벤치마크 (행렬 곱셈)")

    results = {}

    try:
        import mlx.core as mx

        sizes = [1024, 2048, 4096]

        for size in sizes:
            # 랜덤 행렬 생성
            a = mx.random.normal((size, size))
            b = mx.random.normal((size, size))

            # 워밍업 (첫 실행은 컴파일 시간 포함)
            warmup = mx.matmul(a, b)
            mx.eval(warmup)

            # 벤치마크 (5회 평균)
            times = []
            for _ in range(5):
                start = time.perf_counter()
                c = mx.matmul(a, b)
                mx.eval(c)  # MLX는 lazy evaluation이므로 eval 필요
                elapsed = time.perf_counter() - start
                times.append(elapsed)

            avg_ms = (sum(times) / len(times)) * 1000
            gflops = (2 * size**3) / (avg_ms / 1000) / 1e9

            results[f"{size}x{size}"] = {
                "avg_ms": round(avg_ms, 2),
                "gflops": round(gflops, 1),
            }

            success(f"{size}×{size}: {avg_ms:.2f}ms ({gflops:.1f} GFLOPS)")

    except ImportError:
        warn("MLX 미설치로 벤치마크 건너뜀")
    except Exception as e:
        error(f"벤치마크 실패: {e}")

    return results


def check_memory_status() -> dict:
    """현재 메모리 상태 확인"""
    header("5. 메모리 상태")

    result = {}

    try:
        import psutil

        mem = psutil.virtual_memory()
        result["total_gb"] = round(mem.total / (1024**3), 1)
        result["available_gb"] = round(mem.available / (1024**3), 1)
        result["used_percent"] = mem.percent

        info(f"전체: {result['total_gb']}GB")
        info(f"사용 가능: {result['available_gb']}GB")
        info(f"사용률: {result['used_percent']}%")

        # 모델 로드 가능 여부 추정
        available = result["available_gb"]
        if available >= 50:
            success(f"70B 4-bit 모델 로드 가능 (예상 ~40GB, 여유 {available-40:.0f}GB)")
        elif available >= 25:
            success(f"32B 4-bit 모델 로드 가능 (예상 ~18GB, 여유 {available-18:.0f}GB)")
        elif available >= 10:
            warn(f"소형 모델만 로드 가능 (사용 가능: {available:.0f}GB)")
        else:
            error(f"모델 로드를 위한 메모리 부족 (사용 가능: {available:.0f}GB)")
    except ImportError:
        warn("psutil 미설치로 메모리 확인 불가")

    return result


def print_summary(plat: dict, pkgs: dict, gpu: dict, bench: dict, mem: dict):
    """최종 요약 리포트"""
    header("결과 요약")

    try:
        from rich.table import Table

        table = Table(title="Antigravity-K 환경 검증 결과")
        table.add_column("항목", style="cyan")
        table.add_column("상태", style="green")
        table.add_column("비고")

        # 플랫폼
        is_mac = plat.get("is_apple_silicon", False)
        table.add_row(
            "Apple Silicon",
            "✓" if is_mac else "✗",
            f"{plat['arch']}" if is_mac else "Mac 이동 후 확인"
        )

        # MLX
        mlx_ok = pkgs.get("mlx") is not None
        table.add_row(
            "MLX Framework",
            "✓" if mlx_ok else "✗",
            pkgs.get("mlx", "미설치")
        )

        # Metal GPU
        table.add_row(
            "Metal GPU",
            "✓" if gpu.get("available") else "✗",
            gpu.get("device", "N/A")
        )

        # 메모리
        mem_gb = mem.get("total_gb", 0)
        table.add_row(
            "Memory",
            "✓" if mem_gb >= 32 else "!",
            f"{mem_gb}GB" if mem_gb else "확인 불가"
        )

        # 벤치마크
        if bench:
            best = list(bench.values())[-1]
            table.add_row(
                "벤치마크",
                "✓",
                f"최대 {best['gflops']} GFLOPS"
            )

        console.print(table)

    except ImportError:
        # Rich 없을 때 기본 출력
        print("\n--- 결과 요약 ---")
        print(f"  Apple Silicon: {'✓' if plat.get('is_apple_silicon') else '✗'}")
        print(f"  MLX: {pkgs.get('mlx', '미설치')}")
        print(f"  Metal GPU: {'✓' if gpu.get('available') else '✗'}")
        print(f"  Memory: {mem.get('total_gb', '?')}GB")

    # 다음 단계 안내
    print()
    if not plat.get("is_apple_silicon"):
        info("현재 Windows 환경입니다.")
        info("Mac 도착 후: git clone → setup_env.sh → python verify_mlx.py")
    elif pkgs.get("mlx") is None:
        info("다음 단계: source .venv/bin/activate && pip install -r requirements.txt")
    else:
        success("Phase 1 완료! Phase 2 (추론 엔진) 진행 준비 완료")
        info("다음 단계: python -m src.antigravity_k.engine.inference_server")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Antigravity-K — MLX 환경 검증 & 벤치마크               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    plat = check_platform()
    pkgs = check_mlx_packages()
    gpu = check_metal_gpu()
    bench = run_benchmark()
    mem = check_memory_status()

    print_summary(plat, pkgs, gpu, bench, mem)

    # 종료 코드: MLX가 필요한 환경인데 미설치면 1
    if plat.get("is_apple_silicon") and pkgs.get("mlx") is None:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
