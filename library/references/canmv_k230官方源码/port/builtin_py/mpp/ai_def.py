import uctypes

k_ai_chn_param_desc = {
    "usr_frame_depth": 0 | uctypes.UINT32,
}

def k_ai_chn_param_parse(s, kwargs):
    s.usr_frame_depth = kwargs.get("usr_frame_depth", 0)

k_ai_chn_pitch_shift_param_desc = {
    "semitones": 0 | uctypes.INT32,
}

def k_ai_chn_pitch_shift_param_parse(s, kwargs):
    s.semitones = kwargs.get("semitones", 0)

k_ai_vqe_enable_desc = {
    "aec_enable": 0 | uctypes.UINT32,
    "aec_echo_delay_ms": 4 | uctypes.UINT32,
    "agc_enable": 8 | uctypes.UINT32,
    "ans_enable": 12 | uctypes.UINT32,
}

def k_ai_vqe_enable_parse(s, kwargs):
    s.aec_enable = kwargs.get("aec_enable", 0)
    s.aec_echo_delay_ms = kwargs.get("aec_echo_delay_ms", 0)
    s.agc_enable = kwargs.get("agc_enable", 0)
    s.ans_enable = kwargs.get("ans_enable", 0)