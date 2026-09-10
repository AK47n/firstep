// 取证探针（工单 batch-runner-self-heal/01）：**挂死**——不退出，等批跑器 --timeout 杀。
// 用于验证「脚本超时被杀 → 判挂死」以及挂死支次的落盘与恢复（重建标签页）。
// 用法：node .scratch/batch-runner-self-heal/probe-hang.mjs
console.log("挂死探针：本进程刻意不退出，等待批跑器超时杀掉");
setInterval(() => {}, 1000);
