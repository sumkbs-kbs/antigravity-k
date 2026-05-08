# Python package release scaffold

이 저장소의 Python 패키지는 `python-packages/*` 아래에 둘 계획이다.

현재는 실제 패키지가 없어서 release-please workflow만 껍데기 상태로 남겨 둔다.

첫 Python 패키지를 추가할 때 해야 할 일:

1. `python-packages/<package-name>/pyproject.toml` 생성
2. `.github/release-please/python-config.json`에 해당 path와 `release-type: "python"` 추가
3. `.github/release-please/python-manifest.json`에 시작 버전 추가
4. `release-python.yml`에 build + `pypa/gh-action-pypi-publish` publish job 연결

주의:

- PyPI trusted publishing은 현재 reusable workflow 안에서 쓰지 않는 것이 안전하다.
- 실제 `pypi-publish` job은 지금처럼 top-level workflow에 두는 기준으로 유지한다.
