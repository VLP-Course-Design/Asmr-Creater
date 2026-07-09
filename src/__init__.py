"""ASMR Creater —— 从图像生成空间化 ASMR 白噪音。

分层(通过 Scene Contract JSON 解耦,可并行开发、随意替换底层模型):
    common  契约加载与校验(共用)
    vision  图 → JSON
    audio   JSON → 声音
    ui      集成 + Web 界面
"""

__version__ = "0.1.0"
