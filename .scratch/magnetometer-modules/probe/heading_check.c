/* 航向角语义离线复核（真机前先行验证，不碰硬件）。
 * 直接编译两份模块真源的 heading 纯函数（剥离 include 后原样拷入），
 * 与 C 库 atan2 逐步比对：方向语义 / 0–360 归一 / 零向量 / 两件互替一致性。
 * 构建：gcc -O2 -o heading_check heading_check.c -lm
 * （mspm0 版源码原样在 hmc5883l.c / qmc5883l.c 的 heading_from_xy；
 *   此处逐字节照抄函数体，仅去掉 DL_GPIO/math.h 依赖——qmc 用 atan2f，
 *   故本机以 atan2 + 57.29578f 复刻等价语义。） */

#include <stdio.h>
#include <math.h>

#define HMC5883L_RAD_TO_DEG 57.29577951308232f

/* ---- 照抄 library/modules/hmc5883l/code/hmc5883l.c 的 hmc5883l_heading_from_xy ---- */
static float hmc5883l_heading_from_xy(float x, float y)
{
    float ax;
    float ay;
    float base;
    float deg;

    if (x == 0.0f && y == 0.0f) {
        return 0.0f;
    }
    ax = (x < 0.0f) ? -x : x;
    ay = (y < 0.0f) ? -y : y;
    if (ay <= ax) {
        float z = ay / ax;
        float z2 = z * z;
        base = z * (0.9998660f
                    - z2 * (0.3302995f
                            - z2 * (0.1801410f
                                    - z2 * (0.0851330f - z2 * 0.0208351f))));
    } else {
        float z = ax / ay;
        float z2 = z * z;
        base = 1.5707963f
               - z * (0.9998660f
                      - z2 * (0.3302995f
                              - z2 * (0.1801410f
                                      - z2 * (0.0851330f - z2 * 0.0208351f))));
    }
    if (x < 0.0f) {
        base = 3.1415927f - base;
    }
    if (y < 0.0f) {
        base = -base;
    }
    deg = base * HMC5883L_RAD_TO_DEG;
    if (deg < 0.0f) {
        deg += 360.0f;
    }
    if (deg >= 360.0f) {
        deg -= 360.0f;
    }
    return deg;
}

/* ---- 照抄 library/modules/qmc5883l/code/qmc5883l.c 的 qmc5883l_heading_from_xy ---- */
static float qmc5883l_heading_from_xy(float x, float y)
{
    float deg;

    if ((x == 0.0f) && (y == 0.0f)) {
        return 0.0f;
    }
    deg = (float)atan2((double)y, (double)x) * 57.29578f;
    while (deg < 0.0f) {
        deg += 360.0f;
    }
    while (deg >= 360.0f) {
        deg -= 360.0f;
    }
    return deg;
}

static int fails = 0;

static void expect_near(const char *what, double got, double want, double tol)
{
    double d = fabs(got - want);

    if (d > tol) {
        printf("  FAIL %-46s got=%9.4f want=%9.4f diff=%.4f\n", what, got, want, d);
        fails++;
    } else {
        printf("  ok   %-46s got=%9.4f want=%9.4f diff=%.4f\n", what, got, want, d);
    }
}

int main(void)
{
    /* 1) 方向语义锚点：+X = 0°（北）、+Y = 90°（东）、-X = 180°、-Y = 270° */
    printf("[1] 方向语义锚点（X 指北、Y 指东、顺时针为正）\n");
    expect_near("hmc (+1, 0) -> 0", hmc5883l_heading_from_xy(1, 0), 0.0, 0.05);
    expect_near("hmc ( 0,+1) -> 90", hmc5883l_heading_from_xy(0, 1), 90.0, 0.05);
    expect_near("hmc (-1, 0) -> 180", hmc5883l_heading_from_xy(-1, 0), 180.0, 0.05);
    expect_near("hmc ( 0,-1) -> 270", hmc5883l_heading_from_xy(0, -1), 270.0, 0.05);
    expect_near("qmc (+1, 0) -> 0", qmc5883l_heading_from_xy(1, 0), 0.0, 0.05);
    expect_near("qmc ( 0,+1) -> 90", qmc5883l_heading_from_xy(0, 1), 90.0, 0.05);
    expect_near("qmc (-1, 0) -> 180", qmc5883l_heading_from_xy(-1, 0), 180.0, 0.05);
    expect_near("qmc ( 0,-1) -> 270", qmc5883l_heading_from_xy(0, -1), 270.0, 0.05);

    /* 2) 零向量 / 负零：不得出 NaN */
    printf("[2] 零向量与 -0.0\n");
    expect_near("hmc (0,0) -> 0", hmc5883l_heading_from_xy(0, 0), 0.0, 1e-6);
    expect_near("qmc (0,0) -> 0", qmc5883l_heading_from_xy(0, 0), 0.0, 1e-6);
    expect_near("hmc (-0.0, 0) -> 0", hmc5883l_heading_from_xy(-0.0f, 0), 0.0, 1e-6);
    expect_near("qmc (-0.0, 0) -> 0", qmc5883l_heading_from_xy(-0.0f, 0), 0.0, 1e-6);

    /* 3) 全周扫描：与 atan2 参考比 + 两件互替差（同 x/y 出角应一致） */
    printf("[3] 全周 1° 步进：与 atan2 参考差 / 两件互替差\n");
    {
        double worst_ref = 0.0, worst_x = 0.0;
        double worst_ref_at = 0.0, worst_x_at = 0.0;
        int i;
        for (i = 0; i < 360; i++) {
            double rad = (double)i * 3.14159265358979 / 180.0;
            float x = (float)cos(rad);
            float y = (float)sin(rad);
            double want = (double)i;
            double hh = hmc5883l_heading_from_xy(x, y);
            double hq = qmc5883l_heading_from_xy(x, y);
            double dref = fabs(hh - want);
            double dx = fabs(hh - hq);
            if (dref > 180.0) dref = 360.0 - dref;
            if (dx > 180.0) dx = 360.0 - dx;
            if (dref > worst_ref) { worst_ref = dref; worst_ref_at = want; }
            if (dx > worst_x) { worst_x = dx; worst_x_at = want; }
        }
        printf("  hmc 逼近 vs atan2 参考：最大偏差 %.4f° (at %.0f°)\n", worst_ref, worst_ref_at);
        printf("  hmc vs qmc 同输入出角：最大差 %.4f° (at %.0f°)\n", worst_x, worst_x_at);
        if (worst_ref > 0.05) { printf("  FAIL hmc 逼近超 0.05°（manifest 声称 ±0.01° 级）\n"); fails++; }
        if (worst_x > 0.05) { printf("  FAIL 两件互替出角不一致 >0.05°（换芯片只改头文件名会变读数）\n"); fails++; }
    }

    /* 4) 真实量级（±8G @ 1090 LSB/G 的典型水平地磁读数）下的量化误差 */
    printf("[4] 真实量级（几 k LSB）方向语义仍成立\n");
    expect_near("hmc (2000, 0) -> 0", hmc5883l_heading_from_xy(2000, 0), 0.0, 0.05);
    expect_near("hmc (0, 2000) -> 90", hmc5883l_heading_from_xy(0, 2000), 90.0, 0.05);
    expect_near("hmc (1500, 1500) -> 45", hmc5883l_heading_from_xy(1500, 1500), 45.0, 0.05);
    expect_near("hmc (-1500, 1500) -> 135", hmc5883l_heading_from_xy(-1500, 1500), 135.0, 0.05);
    expect_near("hmc (-1500, -1500) -> 225", hmc5883l_heading_from_xy(-1500, -1500), 225.0, 0.05);

    /* 5) 硬铁偏移入参语义：read_heading 里 deg = f(x - x_off, y - y_off) */
    printf("[5] 硬铁偏移入参（(x-x_off, y-y_off) 后应回到 0°）\n");
    {
        float x = 2500.0f, y = 700.0f, xo = 500.0f, yo = 700.0f;
        expect_near("hmc (2500-500, 700-700) -> 0",
                    hmc5883l_heading_from_xy(x - xo, y - yo), 0.0, 0.05);
    }

    printf("\n%s（fails=%d）\n", fails ? "存在失败项" : "全部通过", fails);
    return fails ? 1 : 0;
}
