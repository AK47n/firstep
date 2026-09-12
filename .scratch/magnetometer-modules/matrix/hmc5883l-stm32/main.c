#include "headfile.h"
#include "hmc5883l_stm32.h"
int main(void) { int16_t x = 0, y = 0, z = 0; float deg = 0.0f;
  uint8_t st = hmc5883l_init(); (void)st;
  (void)hmc5883l_read(&x, &y, &z);
  (void)hmc5883l_read_heading(&deg, 0, 0);
  while (1) {} }
