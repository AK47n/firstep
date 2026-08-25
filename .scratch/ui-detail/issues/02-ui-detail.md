# 02 动效令牌化：时长/缓动统一（ui-detail）

Status: resolved

## 验收标准

- [ ] :root 定义 --dur-fast / --dur-base / --dur-slow / --ease-ui 令牌
- [ ] 主要 UI 过渡采样替换为令牌：tab nav、按钮、卡片、折叠图标、step-nav、ov-chip、toast in/out、card-step-status
- [ ] 特色动画保留（btn-breathe / celebrate / ovFillPulse / prog-bar / brand-blink）
- [ ] 内联 script 两块语法解析 OK；node --test 全绿
- [ ] 中文提交信息
