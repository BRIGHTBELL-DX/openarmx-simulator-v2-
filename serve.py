#!/usr/bin/env python3
"""
OpenArmX Robot Simulator - HTTP Server
로컬 STL 메시 파일을 서빙하는 Python HTTP 서버
실행: python serve.py
"""
import http.server
import socketserver
import os
import sys
import webbrowser
import urllib.parse
import json

DANCE_PROMPT = """너는 로봇팔 댄스 시퀀스 디렉터다.

사용자가 입력한 전체 길이는 {duration}초다.
N={duration}으로 간주하고, 마지막 time은 반드시 {duration}.0으로 끝내라.

사용자가 입력한 전체 길이 N초에 맞춰 로봇팔 댄스 시퀀스를 JSON 배열로 생성해라.

[입력값]
- 전체 길이: N초
- 예: N=15, N=30, N=45, N=60

[출력 형식]
- JSON 배열만 출력한다.
- 설명 문장, 제목, markdown 코드블록은 출력하지 않는다.
- transition_id는 모든 항목에서 "1"로 고정한다.
- 각 항목은 반드시 아래 형식을 따른다.

[
  {{
    "transition_id": "1",
    "time": 0.0,
    "pose_id": "P-001"
  }}
]

[시간 조건]
- time은 반드시 0.0초부터 시작한다.
- 마지막 time은 반드시 N.0초로 끝난다.
- time은 소수점 1자리까지 사용한다.
- 시작은 반드시 P-001 또는 P-002에서 시작한다.
- 마지막은 반드시 P-002 → P-001 → P-001 흐름으로 원래 자세에 복귀한다.
- 마지막 복귀 구간은 전체 길이 N초 기준 마지막 1초 이내에 배치한다.

[포즈 간격 조건]
- 기본 포즈 간격은 0.4~0.7초를 중심으로 구성한다.
- 일반 리듬 동작은 0.4~0.6초 간격을 우선 사용한다.
- 큰 액션 동작은 0.6~0.8초 간격까지 허용한다.
- 웨이브 동작은 0.45~0.65초 간격으로 이어서 흐름이 끊기지 않게 한다.
- 포인트 포즈를 홀드해야 할 경우에도 0.8초를 넘기지 않는다.
- 1.0초 이상 유지되는 구간은 만들지 않는다.
- 같은 pose_id를 연속으로 반복하는 홀드는 특별한 의도가 있을 때만 사용한다.
- 의미 없는 긴 홀드는 피한다.

[전체 구성 원칙]
특정 스타일명을 먼저 정하지 말고, 사용 가능한 포즈 전체를 자유롭게 조합한다.
단, 단순 랜덤 나열이 아니라 실제 춤처럼 보이도록 흐름, 대비, 반복, 변주를 고려한다.

[구간 구성]
전체 길이 N초를 대략 아래 비율로 구성한다.

- 0~20%: 시작과 첫 번째 포인트
- 20~45%: 리듬 변화와 비대칭 동작
- 45~65%: 웨이브, 팝 히트, 컷팅 등 중간 포인트
- 65~85%: 큰 액션, 오픈/인워드 대비
- 85~100%: 피날레 후 원래 자세 복귀

단, 구간명은 출력하지 말고 JSON 배열만 출력한다.

[반드시 포함할 동작 성격]
30초 이상일 경우 아래 동작 성격 중 최소 5가지를 포함한다.
30초 미만일 경우 최소 4가지를 포함한다.

1. 양팔을 크게 여는 오픈 동작
2. 팔이 몸 안쪽으로 들어오는 인워드/허그 동작
3. 좌우가 다른 비대칭 동작
4. 위아래 낙차가 큰 업다운 동작
5. 손끝에서 반대 손끝으로 흐르는 웨이브 동작
6. 짧게 찍는 팝/히트 동작
7. 한쪽 팔만 주도하는 원암 동작
8. 마지막을 정리하는 릴리즈/복귀 동작

[다양성 규칙]
- 같은 포즈군만 길게 반복하지 않는다.
- 같은 카테고리 포즈를 5개 이상 연속으로 사용하지 않는다.
- 대칭 포즈만 계속 사용하지 않는다.
- 비대칭 포즈만 계속 사용하지 않는다.
- 웨이브 포즈만 길게 반복하지 않는다.
- 허그/인워드 포즈만 길게 반복하지 않는다.
- 큰 오픈 포즈 뒤에는 인워드, 컷팅, 웨이브, 다운 동작 중 하나로 대비를 만든다.
- 몸 안쪽으로 들어오는 포즈 뒤에는 릴리즈 또는 오픈 포즈를 배치한다.
- 웨이브 피크 포즈 뒤에는 앵커, 릴리즈, 오픈 포즈 중 하나를 배치한다.
- 생성할 때마다 포즈 순서, 분위기, 구간 비중이 달라지게 한다.
- 내부적으로는 하나의 흐름을 만들되, 컨셉명은 출력하지 않는다.

[사용 가능한 포즈군]
- 기본/복귀: P-001, P-002
- K-POP 포인트: P-049~P-060, P-079~P-084
- 사이드/프론트 웨이브: P-061~P-078
- 가드/헌트릭스/바디 크로스: P-085~P-092
- 웨이브 히트/팝핀: P-093~P-102
- 샤프 컷/휩 컷: P-103~P-112
- 인워드 허그: P-113~P-120
- 원암 허그: P-121~P-124
- 다이내믹 액션: P-125~P-136
- 인워드 클로즈: P-137~P-144
- 와이드 웨이브: P-145~P-152
- 익스트림 오픈 웨이브: P-161~P-168

[웨이브 사용 규칙]
웨이브를 사용할 경우 아래 흐름 중 하나를 반드시 포함한다.

정방향 익스트림 오픈 웨이브:
P-161 → P-162 → P-163 → P-164 → P-165 → P-166 → P-167 → P-168

역방향 익스트림 오픈 웨이브:
P-161 → P-167 → P-166 → P-165 → P-164 → P-163 → P-162 → P-168

웨이브는 손끝 → 팔꿈치 → 센터 → 반대 팔꿈치 → 반대 손끝으로 파동이 이어지는 느낌이 나야 한다.
웨이브가 없는 순간에는 P-161 같은 오픈 앵커 포즈를 사용해 팔이 넓게 펼쳐진 상태를 만든다.
웨이브 전체를 너무 길게 반복하지 말고, 30초 안에서는 1회 또는 짧은 변형으로 사용한다.

[주의 포즈]
아래 포즈는 주의 포즈로 간주한다.

P-052, P-053, P-087, P-090, P-091, P-092,
P-094, P-095, P-098, P-099, P-101,
P-103, P-104, P-105, P-107, P-108, P-111,
P-114, P-115, P-116, P-117, P-118, P-119,
P-140, P-143,
P-162, P-163, P-164, P-165, P-166, P-167

주의 포즈는 3개 이상 연속으로 배치하지 않는다.
주의 포즈 앞뒤에는 가능한 한 완충 포즈를 배치한다.

[완충 포즈]
아래 포즈는 완충 포즈로 사용할 수 있다.

P-002, P-043, P-064, P-071, P-102, P-120, P-126, P-145, P-161, P-168

[안전 흐름 규칙]
- 안쪽으로 깊게 들어오는 포즈를 연속 배치하지 않는다.
- 허그/인워드 계열 뒤에는 P-120, P-126, P-002, P-161, P-168 중 하나를 섞어 정리한다.
- 웨이브 피크 뒤에는 P-168, P-161, P-102, P-120 중 하나를 섞어 정리한다.
- 샤프 컷/휩 컷 뒤에는 오픈 또는 릴리즈 포즈를 배치한다.
- 큰 액션 포즈 뒤에는 바로 위험 포즈로 가지 말고 완충 포즈를 거친다.

[마지막 복귀 조건]
마지막은 반드시 전체 길이 N초에 맞춰 아래 구조와 유사하게 끝낸다.

예시: N=30초인 경우
[
  ...
  {{ "transition_id": "1", "time": 29.2, "pose_id": "P-002" }},
  {{ "transition_id": "1", "time": 29.7, "pose_id": "P-001" }},
  {{ "transition_id": "1", "time": 30.0, "pose_id": "P-001" }}
]

예시: N=45초인 경우
[
  ...
  {{ "transition_id": "1", "time": 44.2, "pose_id": "P-002" }},
  {{ "transition_id": "1", "time": 44.7, "pose_id": "P-001" }},
  {{ "transition_id": "1", "time": 45.0, "pose_id": "P-001" }}
]

[최종 생성 지시]
이제 사용자가 입력한 N초에 맞춰 자유 조합형 로봇팔 댄스 시퀀스를 생성해라.
출력은 JSON 배열만 제공한다."""

PORT = 8080
SIM_DIR = os.path.dirname(os.path.abspath(__file__))

# Poses and timeline storage
DATA_FILE = os.path.join(SIM_DIR, 'simulation_data.json')


class SimHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SIM_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api/data':
            self._serve_json(self._load_data())
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/data':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                self._save_data(data)
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif parsed.path == '/api/generate':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                req = json.loads(body)
                duration = req.get('duration', 30)
                self._generate_dance(duration)
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        else:
            self.send_error(404)

    def _generate_dance(self, duration):
        try:
            import anthropic
        except ImportError:
            self._send_json({'ok': False, 'error': 'anthropic 패키지가 설치되지 않았습니다. pip install anthropic'}, 500)
            return

        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            self._send_json({'ok': False, 'error': 'ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.'}, 500)
            return

        try:
            client = anthropic.Anthropic(api_key=api_key)
            prompt = DANCE_PROMPT.format(duration=duration)
            message = client.messages.create(
                model='claude-opus-4-7',
                max_tokens=8192,
                messages=[{'role': 'user', 'content': prompt}]
            )
            result_text = message.content[0].text.strip()
            parsed = json.loads(result_text)
            self._send_json({'ok': True, 'timeline': parsed})
        except json.JSONDecodeError as e:
            self._send_json({'ok': False, 'error': f'JSON 파싱 실패: {e}', 'raw': result_text[:500]}, 500)
        except Exception as e:
            self._send_json({'ok': False, 'error': str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(200)
        self._add_cors()
        self.end_headers()

    def _serve_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._add_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, code=200):
        self._serve_json(obj, code)

    def _add_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def end_headers(self):
        self._add_cors()
        super().end_headers()

    def _load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'poses': {}, 'timeline': []}

    def _save_data(self, data):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def log_message(self, fmt, *args):
        if '/meshes/' not in (args[0] if args else ''):
            print(f'  {args[0] if args else ""}')


def main():
    print()
    print('=' * 55)
    print('  OpenArmX 로봇 시뮬레이터')
    print('=' * 55)
    print(f'  시뮬레이터: {SIM_DIR}')
    print(f'  메시 경로:  {MESH_DIR}')

    if not os.path.exists(MESH_DIR):
        print()
        print('  ⚠️  메시 디렉토리를 찾을 수 없습니다.')
        print('      기본 형상으로 실행됩니다.')

    print()
    print(f'  브라우저 → http://localhost:{PORT}')
    print('  종료: Ctrl+C')
    print('=' * 55)
    print()

    webbrowser.open(f'http://localhost:{PORT}')

    with socketserver.TCPServer(('', PORT), SimHandler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n  서버를 종료합니다.')


if __name__ == '__main__':
    main()
