// GroveLink HUD pieces — also inlined in GroveLinkPhone.txt
// so Sanny still compiles if this include path is wrong.

:DRAW_SHELL
038E: draw_box 548.0 252.0 156.0 328.0 18 20 22 255
038E: draw_box 548.0 250.0 142.0 312.0 28 30 34 255
038E: draw_box 548.0 248.0 128.0 292.0 8 10 12 255
038E: draw_box 548.0 100.0 36.0 5.0 40 42 46 255
038E: draw_box 530.0 100.0 6.0 5.0 40 42 46 255
038E: draw_box 566.0 100.0 6.0 5.0 40 42 46 255
038E: draw_box 548.0 238.0 112.0 252.0 2 16 8 255
038E: draw_box 548.0 118.0 112.0 18.0 0 10 5 255
038E: draw_box 548.0 384.0 22.0 10.0 48 50 54 255
038E: draw_box 548.0 384.0 10.0 10.0 70 72 76 255
038E: draw_box 498.0 122.0 3.0 4.0 40 180 70 255
038E: draw_box 503.0 121.0 3.0 6.0 40 200 80 255
038E: draw_box 508.0 120.0 3.0 8.0 50 220 90 255
038E: draw_box 513.0 119.0 3.0 10.0 60 255 110 255
038E: draw_box 592.0 120.0 16.0 8.0 40 200 80 255
038E: draw_box 601.0 120.0 3.0 4.0 40 200 80 255
00D6: if
0039:   31@ == 1
004D: jf @NO_DOT
038E: draw_box 548.0 118.0 112.0 18.0 0 40 12 255
038E: draw_box 580.0 118.0 8.0 8.0 40 255 90 255
:NO_DOT
033F: set_text_draw_letter_size 0.26 1.02
0340: set_text_draw_rgba 70 255 110 255
0343: set_text_center 1
0348: set_text_draw_proportional 1
0349: set_font 2
033E: display_text 548.0 111.0 'GLTITL'
0051: return

:DRAW_CALL
038E: draw_box 548.0 210.0 96.0 70.0 0 28 10 220
033F: set_text_draw_letter_size 0.24 0.96
0340: set_text_draw_rgba 180 255 180 255
0343: set_text_center 1
0348: set_text_draw_proportional 1
0349: set_font 1
033E: display_text 548.0 168.0 'GLONC'
033F: set_text_draw_letter_size 0.20 0.86
0340: set_text_draw_rgba 200 220 200 255
0343: set_text_center 1
0348: set_text_draw_proportional 1
0349: set_font 1
033E: display_text 548.0 210.0 'GLHANG'
033E: display_text 548.0 328.0 'GLHINT'
0051: return
