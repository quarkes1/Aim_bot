# Aim_bot
# 在Source引擎下基于opencv进行颜色识别，并自动锁定指定颜色的小球

### ！注意 ，需要根据实际灵敏度和屏幕尺寸对参数进行手动调整
#### 必须手动调整的参数
- W，H 调整为屏幕实际的尺寸
- SCALE 根据灵敏度进行调整 此值越大移动的灵敏度越高
#### 其他可选调整参数
- H_TOLERANCE 
- S_TOLERANCE 
- V_TOLERANCE    HSV下对颜色判定的严格程度，越大对颜色判定越宽松
- AIM_THRESHOLD	基础瞄准点击范围
- MIN_AREA / MAX_AREA	过滤过小 / 过大的干扰区域
- LOCK_DURATION	目标锁定时长，防止频繁切换
- DIST_TOLERANCE	等距目标判定容错
