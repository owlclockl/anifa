/* Orthographic, nearest-neighbor triangle rasterizer for the schematic plates.
 * Each vertex is x, y, depth (larger is closer), atlas x, atlas y.
 * Color is premultiplied RGBA; transparent surfaces are drawn back to front. */
#include <math.h>
#include <stddef.h>
#include <stdint.h>

static int clip(int x, int a, int b) { return x < a ? a : (x > b ? b : x); }

void rasterize(int width, int height, uint8_t *rgba, float *depth,
               int texw, int texh, const uint8_t *atlas,
               size_t count, const float *triangles, const float *shade, int translucent) {
    for (size_t i = 0; i < count; i++, triangles += 15, shade += 3) {
        const float *v = triangles, *b = v+5, *c = v+10;
        float ax = b[0]-v[0], ay = b[1]-v[1], bx = c[0]-v[0], by = c[1]-v[1];
        float area = ax*by-ay*bx;
        if (fabsf(area) < 1.e-6f) continue;
        int xl = (int)floorf(fminf(v[0], fminf(b[0], c[0])));
        int yl = (int)floorf(fminf(v[1], fminf(b[1], c[1])));
        int xh = (int)ceilf(fmaxf(v[0], fmaxf(b[0], c[0])));
        int yh = (int)ceilf(fmaxf(v[1], fmaxf(b[1], c[1])));
        if (xl >= width || yl >= height || xh < 0 || yh < 0) continue;
        xl = clip(xl, 0, width-1); xh = clip(xh, 0, width-1);
        yl = clip(yl, 0, height-1); yh = clip(yh, 0, height-1);
        float r0 = by/area, r1 = -bx/area, s0 = -ay/area, s1 = ax/area;
        float du = b[3]-v[3], dv = b[4]-v[4], dz = b[2]-v[2];
        float eu = c[3]-v[3], ev = c[4]-v[4], ez = c[2]-v[2];
        for (int y = yl; y <= yh; y++) {
            float dy = y+0.5f-v[1];
            float dx = xl+0.5f-v[0];
            float r = r0*dx+r1*dy, s = s0*dx+s1*dy;
            for (int x = xl; x <= xh; x++, r += r0, s += s0) {
                if (r < 0.f || s < 0.f || r+s > 1.f) continue;
                size_t p = (size_t)y*width+x;
                float z = v[2]+r*dz+s*ez;
                if (z < depth[p]-1.e-5f) continue;
                int tx = clip((int)floorf(v[3]+r*du+s*eu), 0, texw-1);
                int ty = clip((int)floorf(v[4]+r*dv+s*ev), 0, texh-1);
                const uint8_t *src = atlas+4*((size_t)ty*texw+tx);
                int a = src[3];
                if (a == 0 || (!translucent && a < 128)) continue;
                uint8_t *out = rgba+4*p;
                if (!translucent || a == 255) {
                    depth[p] = z;
                    for (int j = 0; j < 3; j++) out[j] = (uint8_t)fminf(src[j]*shade[j]+.5f, 255.f);
                    out[3] = 255;
                } else {
                    for (int j = 0; j < 3; j++) {
                        int color = (int)fminf(src[j]*shade[j]+.5f, 255.f);
                        out[j] = (uint8_t)((a*color+(255-a)*out[j]+127)/255);
                    }
                    out[3] = (uint8_t)(a+((255-a)*out[3]+127)/255);
                }
            }
        }
    }
}
