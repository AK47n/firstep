#include "headfile.h"
#include "filter.h"

void filter_init(SlidingFilter *f, int32_t *buf, uint8_t size)
{
    f->buf   = buf;
    f->size  = size;
    f->idx   = 0;
    f->count = 0;
    f->sum   = 0;

    for (uint8_t i = 0; i < size; i++)
        buf[i] = 0;
}

int32_t filter_add(SlidingFilter *f, int32_t val)
{
    // 窗口未满：直接加入
    if (f->count < f->size)
    {
        f->buf[f->idx] = val;
        f->sum += val;
        f->idx = (f->idx + 1) % f->size;
        f->count++;
        return (int32_t)(f->sum / f->count);
    }

    // 窗口已满：减去旧值，加入新值
    f->sum -= f->buf[f->idx];
    f->buf[f->idx] = val;
    f->sum += val;
    f->idx = (f->idx + 1) % f->size;

    return (int32_t)(f->sum / f->size);
}

int32_t filter_get(SlidingFilter *f)
{
    if (f->count == 0) return 0;
    return (int32_t)(f->sum / f->count);
}

void filter_reset(SlidingFilter *f)
{
    f->idx   = 0;
    f->count = 0;
    f->sum   = 0;
    for (uint8_t i = 0; i < f->size; i++)
        f->buf[i] = 0;
}
