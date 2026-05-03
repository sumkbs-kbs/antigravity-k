from antigravity_k.engine.protocol_translator import ProtocolTranslator, APIFormat
body = {"model": "deepseek-r1:70b", "messages": [{"role": "user", "content": "안녕"}], "stream": True, "agent_mode": True}
translator = ProtocolTranslator()
fmt = translator.detect_format(body)
req = translator.translate_request(body, source=fmt)
print(f"Format: {fmt}")
print(f"Model: {req.get('model')}")
