#include "ti_msp_dl_config.h"
#include "hmc5883l.h"
int main(void) { int16_t x = 0, y = 0, z = 0; float deg = 0.0f;
  uint8_t st = hmc5883l_init(); (void)st;
  (void)hmc5883l_read(&x, &y, &z);
  (void)hmc5883l_read_heading(&deg, 0, 0);
  deg = hmc5883l_heading_from_xy((float)x, (float)y); (void)deg;
  while (1) {} }
