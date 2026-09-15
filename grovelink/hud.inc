:DRAW_SHELL
038E: draw_box 548.0 250.0 150.0 318.0 26 28 32 255
038E: draw_box 548.0 248.0 126.0 286.0 10 12 14 255
038E: draw_box 548.0 236.0 110.0 246.0 4 20 10 255
038E: draw_box 548.0 124.0 110.0 24.0 4 16 8 255
038E: draw_box 548.0 106.0 40.0 6.0 42 44 48 255
038E: draw_box 548.0 380.0 20.0 20.0 52 54 58 255
038E: draw_box 500.0 126.0 4.0 6.0 50 210 80 255
038E: draw_box 506.0 124.0 4.0 10.0 50 210 80 255
038E: draw_box 512.0 122.0 4.0 14.0 50 210 80 255
00D6: if
0039:   31@ == 1
004D: jf @NO_DOT
038E: draw_box 592.0 124.0 12.0 12.0 40 230 80 255
:NO_DOT
033F: set_text_draw_letter_size 0.28 1.10
0340: set_text_draw_rgba 80 255 120 255
0343: set_text_center 1
0348: set_text_draw_proportional 1
0349: set_font 2
033E: display_text 548.0 116.0 'GLTITL'
0051: return

:DRAW_CALL
033F: set_text_draw_letter_size 0.24 0.96
0340: set_text_draw_rgba 180 255 180 255
0343: set_text_center 1
0348: set_text_draw_proportional 1
0349: set_font 1
033E: display_text 548.0 170.0 'GLONC'
033F: set_text_draw_letter_size 0.20 0.86
0340: set_text_draw_rgba 200 220 200 255
0343: set_text_center 1
0348: set_text_draw_proportional 1
0349: set_font 1
033E: display_text 548.0 210.0 'GLHANG'
0051: return
