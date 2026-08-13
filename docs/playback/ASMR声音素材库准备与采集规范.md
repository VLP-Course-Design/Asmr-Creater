# ASMR 声音素材库准备与采集规范

**版本：** 1.1  
**适用输入：** `scene_type_vocabulary.json` 1.0、视觉记录规范 2.3  
**目标规模：** 约 10～20 类核心场景环境音、66 类视觉锚点关联声音  
**用途：** 图片驱动的助眠环境声、单声道回退及 HRTF 双耳播放

## 1. 结论与数量修正

经核对：

- `scene_type_vocabulary.json` 包含 **20 个场景大组、424 个叶子场景类型**。
- 语义修订表定义了 **66 个受控 `sound_id`**，每个声音对应一个或多个具体可检测视觉锚点。
- 视觉规范2.3不再使用 `bird`、`keyboard`、`cup` 等过宽对象类别，而使用 `visible_bird`、`hands_on_keyboard_typing`、`hand_holding_cup` 等表格化视觉证据。
- 66表示声音类别数量，不是合理的最终文件总数。每类只有一份素材可以建立闭环，但无法避免机械重复。

因此建议将用户提出的数量按以下方式落实：

| 阶段 | 环境音 | 触发音 | 覆盖策略 |
|---|---:|---:|---|
| 最小闭环 | 10～20份场景环境母版 | 66类×每类至少1份，合计至少66份 | 验证所有映射和播放模式；允许暂时重复但不适合正式上线 |
| 正式MVP | 重点环境族每类2个变体，约20～40份 | 66类；循环类至少2份、随机触发类至少3份，约170～200份 | 防止循环和触发机械重复 |
| 稳定版 | 按昼夜、天气和空间大小补到约35～60份 | 高频类别4～6份、低频类别至少3份，约220～300份 | 根据真实数据分布和试听扩充 |

如果当前预算严格限制为约66个文件，应当为66个 `sound_id` 各准备一份，以保证语义覆盖；同时将此版本标记为“最小闭环素材库”，不能称为最终生产库。第二轮应优先为随机触发音补足3个变体，为循环音补足2个不同底景。

## 2. 受控词表与素材库边界

### 2.1 环境音边界

环境音配置只能由 `scene_type_vocabulary.json` 的叶子场景及其 `scene_group` 映射得到。

424 个场景不需要 424 个独立声音。多个相近叶子场景共享 10～20 个环境声配置族，决策层使用：

```text
scene_type 精确映射
  → scene_group 配置族回退
  → indoor_roomtone / open_nature / pink_noise / silence
```

环境素材不得因为画面中存在单个物体而改变主场景语义；例如卧室里的杯子仍以室内房间底景为主，杯子只可能产生低概率触发音。

### 2.2 触发音边界

视觉锚点关联声音必须由视觉规范2.3中的 `initial_visual_anchor_id` 经过 `anchor_sound_mapping_reference` 或独立版本化静态映射得到：

```text
visual anchor_id → trigger mapping → sound_id → asset_id
```

禁止：

- 在检测模型中直接输出素材路径或 `asset_id`；
- 将 `confidence` 直接当音量；
- 为没有证据的普通 `person` 配人声；
- 为暂未覆盖的锚点强行复用不相符素材；
- 在素材文件名中使用自由文本类别。

## 3. MVP 环境音清单

下面列出 20 份建议优先准备的环境母版。表中的叶子场景示例均来自当前 `scene_type_vocabulary.json`；正式映射文件应继续覆盖相应场景组内的其他叶子类型。

| # | `sound_id` | 主要受控场景或场景组 | 建议内容 | MVP 时长 |
|---:|---|---|---|---:|
| 1 | `open_nature_wind` | `natural_terrain`：`mountain`、`hill`、`valley`、`grassland`、`meadow` | 柔和开阔风、极远自然底景，无强鸟叫 | 90～120 s |
| 2 | `arid_wind` | `desert`、`sand_dunes`、`badlands`、`plateau` | 低动态干燥风，去除沙粒猛烈撞击 | 60～120 s |
| 3 | `snow_wind_soft` | `tundra`、`glacier`、`ice_field`、`snowfield`、`polar_landscape` | 柔化寒风，不含暴风尖啸 | 60～120 s |
| 4 | `forest_day_bed` | `forest_vegetation`：`forest`、`woodland`、`grove`、`garden`、`park` | 树叶、轻风、极稀疏远鸟；不含近距离突发鸟鸣 | 90～120 s |
| 5 | `wetland_night_bed` | `wetland`、`marsh`、`swamp`、`bog`、`mangrove` | 稳定虫鸣、极低密度蛙鸣；控制高频疲劳 | 60～120 s |
| 6 | `ocean_coast_bed` | `water_coastal`：`ocean`、`sea`、`beach`、`coast`、`shoreline`、`island` | 中远距离海浪，避免单次巨浪和近距离爆裂 | 90～120 s |
| 7 | `freshwater_flow_bed` | `river`、`stream`、`creek`、`canal`、`waterway`、`waterfall` | 连续溪流或远瀑；避免尖锐水滴占主导 | 60～120 s |
| 8 | `rain_surface_bed` | `sky_weather` 中的 `storm_landscape`、`thunderstorm_landscape`；也可供明确雨景配置使用 | 均匀细雨或雨打稳定表面；不含雷声、车笛 | 90～120 s |
| 9 | `rural_bed` | `agriculture_rural`：`farm`、`farmland`、`pasture`、`rural_village`、`country_road` | 风、草、远虫；牲畜声保持极远且稀疏 | 60～120 s |
| 10 | `urban_distant_bed` | `urban_outdoor`：`street`、`residential_area`、`downtown`、`cityscape`、`suburb` | 去鸣笛的远处交通、稳定城市底噪 | 60～120 s |
| 11 | `transport_exterior_bed` | `transport_outdoor`：`road`、`highway`、`railway`、`bridge`、`tunnel`、`port_terminal` | 平稳远交通或轨道底景；不含刹车尖叫 | 60～120 s |
| 12 | `transport_cabin_bed` | `transport_indoor`：`subway_interior`、`train_interior`、`car_interior`、`airplane_cabin`、`ship_interior` | 稳定低频运行声，无广播、提示音和对话 | 60～120 s |
| 13 | `indoor_roomtone` | `residential_indoor`：`living_room`、`bedroom`、`home_office`；以及 `food_hospitality` 中的 `hotel_room` | 安静房间底噪、极低通风声 | 60～120 s |
| 14 | `study_office_bed` | `residential_indoor`、`workplace_industrial` 与 `education_research` 中的 `study_room`、`office`、`private_office`、`library`、`reading_room` | 安静室内底景；键盘和翻页留给触发层 | 60～120 s |
| 15 | `cafe_hospitality_bed` | `food_hospitality`：`cafe`、`coffee_shop`、`restaurant`、`tea_house`、`hotel_lobby` | 模糊低语和低密度杯碟，不能听清句子 | 60～120 s |
| 16 | `public_interior_murmur` | `retail_personal_service`、`culture_entertainment`、`healthcare_civic_security` 中的公共室内 | 非语言化远人群、轻通风，无广播和收银提示 | 60～120 s |
| 17 | `mechanical_hum_soft` | `workplace_industrial`：`factory`、`warehouse`、`server_room`、`control_room`；以及 `laundromat` | 经过柔化的稳定机械低鸣，无冲压、警报和撞击 | 60～120 s |
| 18 | `large_hall_roomtone` | `religion_heritage` 和大型室内：`church`、`cathedral`、`temple`、`mosque`、`palace`、`concert_hall` | 宽阔安静空间底噪和自然混响尾部，无仪式语言 | 60～120 s |
| 19 | `recreation_distant_bed` | `sports_recreation` 与 `events_social` 中可安全映射的 `picnic_area`、`campsite`、`hiking_trail`、`community_gathering` | 极远活动底景；热闹赛事、抗议、音乐会默认不映射或安全回退 | 60～120 s |
| 20 | `animal_facility_distant_bed` | `animal_facilities`：`zoo`、`wildlife_sanctuary`、`aviary`、`fish_farm` 等 | 低密度远动物底景，无近距离吼叫、犬吠和尖叫 | 60～120 s |

### 3.1 特殊场景处理

- `non_scene:none`：默认静音，不需要录制“none”素材；用户主动选择时才使用程序生成粉红或棕噪声。
- `sky`、`cloudscape`、`rainbow_sky`、`eclipse_sky`：画面本身没有明确声源，应回退到主空间场景或静音，不能因为“天空”自动加风。
- `thunderstorm_landscape`：MVP 环境层可使用无雷或极远雷的雨；`distant_thunder` 应作为低概率触发音单独管理。
- `nightclub`、`concert_event`、`sports_event`、`protest_scene`、`emergency_room`、`police_station` 等不适合助眠的场景：转换为柔和远底景或静音，不采集真实高刺激版本作为默认素材。
- `underwater`、`seabed`：需要专门水下素材时再扩展；MVP 不应简单复用海面海浪。

## 4. 66类视觉锚点关联声音清单

### 4.1 数量与角色定义

下面66项与语义修订表及视觉规范2.3的 `reference_sound_id` 完全一致。其中既包含连续循环层，也包含间歇纹理和一次性随机触发。这里的“触发音表”表示它们由视觉锚点触发候选生成，并不表示所有素材都是短促的一次性声音。

| 角色 | 建议母版时长 | 最小闭环变体 | 正式MVP变体 |
|---|---:|---:|---:|
| 连续循环 `loop` | 30～120 s，优先60～120 s | 1 | 至少2 |
| 间歇纹理 `texture` | 8～30 s | 1 | 至少2～3 |
| 随机触发 `trigger` | 0.3～8 s | 1 | 至少3 |
| 长共振触发 `long_tail_trigger` | 5～20 s | 1 | 至少3 |

### 4.2 完整清单

| # | `sound_id` | 主要视觉 `anchor_id` | 角色 | 单条推荐时长 | 采集与助眠重点 |
|---:|---|---|---|---:|---|
| 1 | `light_rain` | `visible_rain_streaks`、`umbrella_in_visible_rain` | loop | 60～120 s | 轻柔连续，无雷击和近距离大雨滴 |
| 2 | `rain_on_window` | `rain_dropped_window` | loop | 60～120 s | 控制玻璃敲击高频，接缝不可察觉 |
| 3 | `rain_on_roof` | `roof_or_canopy_in_rain`、`vehicle_roof_in_visible_rain` | loop | 60～120 s | 选择柔和材质，避免铁皮尖响 |
| 4 | `ocean_waves` | `breaking_ocean_waves` | loop | 60～120 s | 中远海浪，无巨浪爆裂和强风 |
| 5 | `shore_lapping` | `calm_shoreline` | loop | 60～120 s | 小幅水拍岸，动态平稳 |
| 6 | `stream_flow` | `visible_stream_flow` | loop | 60～120 s | 连续流动，避免局部尖锐水花 |
| 7 | `waterfall_distant` | `visible_waterfall` | loop | 60～120 s | 使用远瀑版本，限制宽频轰鸣 |
| 8 | `fountain_flow` | `visible_fountain` | loop | 60～120 s | 人工水景稳定，无人声和城市提示音 |
| 9 | `water_drip` | `visible_dripping_water` | trigger | 0.3～2 s | 至少3种滴水，触发间隔不得规律 |
| 10 | `shower_flow` | `running_shower` | loop | 60～120 s | 均匀水流，不含水龙头开关瞬态 |
| 11 | `gentle_wind` | `wind_moved_light_fabric`、`wind_moved_flag`、`wind_bent_grass_or_foliage` | loop | 60～120 s | 无呼啸，保留柔和低频风感 |
| 12 | `leaf_rustle` | `wind_moved_tree_leaves` | loop | 60～120 s | 叶片柔和，避免持续刺耳沙声 |
| 13 | `grass_rustle` | `tall_grass_reeds_or_crops` | loop | 60～120 s | 麦田、芦苇或草丛摩擦，控制高频 |
| 14 | `bamboo_rustle` | `bamboo_forest_close` | loop | 60～120 s | 竹叶为主，只允许少量柔和竹竿碰撞 |
| 15 | `window_wind` | `open_window_moving_curtain` | loop | 60～120 s | 避免窗缝啸叫和室外交通声 |
| 16 | `distant_thunder` | `storm_clouds_or_lightning` | long_tail_trigger | 4～12 s | 只用远雷，极长随机间隔，无炸雷 |
| 17 | `fireplace_crackle` | `burning_fireplace` | loop | 60～120 s | 稀疏木柴噼啪，人工去除爆裂峰值 |
| 18 | `campfire_crackle` | `burning_campfire` | loop | 60～120 s | 户外火焰，避免强风和近距离爆燃 |
| 19 | `cicada_chorus` | `visible_cicada`、`dense_summer_tree_canopy` | loop | 30～90 s | 低音量，高频需柔化 |
| 20 | `cricket_chirp` | `visible_cricket`、`night_grass_or_courtyard` | loop/trigger | 10～60 s或1～4 s | 可准备连续底景和单次鸣叫两种子类型 |
| 21 | `insect_ambience` | `night_low_vegetation` | loop | 30～90 s | 柔和连续虫鸣，避免过密和单频尖鸣 |
| 22 | `bee_buzz` | `visible_bee`、`beehive_or_bee_on_flower` | trigger | 1～5 s | 中远蜂鸣，禁止贴耳绕头 |
| 23 | `bird_chirp` | `visible_bird`、`bird_group_in_flight` | trigger | 1～5 s | 远鸟单次或短组，至少3个不同叫声 |
| 24 | `bird_wing_flutter` | `bird_takeoff_or_landing` | trigger | 0.3～2 s | 柔和振翅，无近距离冲击 |
| 25 | `frog_croak` | `visible_frog`、`frog_at_pond_edge` | trigger | 1～4 s | 单次蛙鸣，控制低频与重复感 |
| 26 | `cat_purr` | `relaxed_or_sleeping_cat` | texture | 8～30 s | 稳定呼噜，无叫声、喘息或触麦 |
| 27 | `distant_livestock` | `livestock_in_pasture` | trigger | 1～5 s | 极远牛羊马声，低概率，无高声叫喊 |
| 28 | `keyboard_typing` | `hands_on_keyboard_typing`、`visible_keyboard` | texture | 8～30 s | 柔和键盘，不用高响机械轴 |
| 29 | `mouse_click` | `hand_on_mouse`、`visible_computer_mouse` | trigger | 0.2～1 s | 去尖峰，极低概率 |
| 30 | `page_turn` | `page_turning_action`、`open_book_magazine_or_notebook` | trigger | 0.8～3 s | 单次翻页，不连续快速翻书 |
| 31 | `paper_rustle` | `visible_paper_or_documents` | trigger | 1～4 s | 轻整理纸张，禁止揉纸爆裂 |
| 32 | `pencil_writing` | `hand_writing_with_pencil` | texture | 5～20 s | 保留柔和摩擦，避免刮擦尖声 |
| 33 | `pen_writing` | `hand_writing_with_pen` | texture | 5～20 s | 钢笔或圆珠笔独立录制，不与铅笔合并 |
| 34 | `book_handling` | `book_handling_action`、`book_stack_or_bookshelf` | trigger | 1～5 s | 取放或整理书本，不摔书 |
| 35 | `clock_tick` | `visible_clock` | loop | 30～120 s | 极低音量；必须支持关闭，避免焦虑 |
| 36 | `fan_hum` | `running_fan` | loop | 60～120 s | 稳定无轴承异响，多个转速分开标记 |
| 37 | `air_conditioner_hum` | `visible_air_conditioner` | loop | 60～120 s | 稳定低鸣，无启停咔哒和提示音 |
| 38 | `refrigerator_hum` | `visible_refrigerator_or_freezer` | loop | 60～120 s | 极低音量，不录压缩机启停冲击 |
| 39 | `washing_machine_hum` | `running_washing_machine` | loop | 60～120 s | 仅平稳洗涤阶段，不录高速脱水震动 |
| 40 | `kettle_simmer` | `steaming_kettle`、`visible_kettle` | texture | 8～30 s | 轻微加热沸腾，不使用鸣笛壶 |
| 41 | `coffee_machine` | `operating_coffee_machine` | trigger/texture | 3～15 s | 控制泵声和蒸汽尖声，无杯子碰撞混入 |
| 42 | `cup_clink` | `hand_holding_cup`、`multiple_cups_or_cup_saucer`、`single_visible_cup` | trigger | 0.3～2 s | 单杯仅为弱推断；素材柔和轻放并限制高频峰值 |
| 43 | `dish_handling` | `table_setting_action`、`visible_tableware` | trigger | 1～4 s | 轻摆碗碟，无摔碰和金属重击 |
| 44 | `door_soft_close` | `hand_on_door`、`partly_open_interior_door` | trigger | 1～3 s | 软关闭，无门锁巨响和恐怖吱嘎 |
| 45 | `fabric_rustle` | `handled_fabric_or_bedding`、`handled_clothing` | trigger/texture | 1～8 s | 布料、床单、毛毯或衣物整理，避免强摩擦 |
| 46 | `broom_sweeping` | `sweeping_action` | texture | 5～20 s | 慢速扫地，不碰撞家具 |
| 47 | `cooking_sizzle` | `active_cooking_pan` | texture | 8～30 s | 柔和煎炒，人工去除油爆峰值 |
| 48 | `soft_footsteps` | `walking_person` | trigger | 2～8 s | 软底鞋慢步，分地面材质做标签 |
| 49 | `crowd_murmur` | `gathered_crowd` | loop | 30～120 s | 不得听清语言，无笑喊和个人信息 |
| 50 | `tableware_ambience` | `occupied_dining_tables`、`visible_tableware` | texture | 8～30 s | 稀疏杯碟，适合与低声人群混合 |
| 51 | `distant_traffic` | `road_vehicle_flow` | loop | 60～120 s | 远车流，无鸣笛、急刹和摩托爆音 |
| 52 | `train_rumble` | `visible_train_or_railway` | loop | 60～120 s | 稳定运行低频，无广播和轨道尖叫 |
| 53 | `subway_rumble` | `visible_subway_train_or_platform` | loop | 60～120 s | 控制刹车高频，不含提示音 |
| 54 | `airplane_cabin_hum` | `airplane_cabin_or_window_wing_view` | loop | 60～120 s | 稳定舱内轰鸣，无广播和乘客对话 |
| 55 | `boat_hull_water` | `boat_hull_at_water` | loop | 60～120 s | 柔和船体拍水，无发动机突变 |
| 56 | `wind_chime` | `visible_wind_chime` | trigger | 1～6 s | 长间隔，控制高频和响度 |
| 57 | `distant_bell` | `large_temple_or_church_bell` | long_tail_trigger | 4～15 s | 远距离低音量，保留自然衰减 |
| 58 | `vinyl_crackle` | `visible_record_player` | loop | 30～120 s | 极低音量，按规则削弱6 kHz以上频段 |
| 59 | `tv_static` | `television_no_signal` | loop | 30～120 s | 不含节目音频，高频严格受控 |
| 60 | `radio_static` | `visible_radio_or_tuning_knob` | texture | 5～20 s | 不含可辨识电台、语言和音乐 |
| 61 | `electronic_hum` | `server_rack_or_lab_electronics` | loop | 60～120 s | 无电流尖鸣、报警和风扇故障声 |
| 62 | `snow_crunch` | `walking_person_on_snow`、`snow_covered_ground` | trigger | 2～8 s | 柔和踩雪，避免破冰尖响 |
| 63 | `blizzard_wind` | `visible_blizzard` | loop | 60～120 s | 控制啸叫，保留低频风噪，不做恐怖效果 |
| 64 | `fireplace_tea_boil` | `kettle_on_fireplace_or_stove` | loop/texture | 30～90 s | 柔和炭火与沉闷水泡，控制爆裂声 |
| 65 | `singing_bowl` | `visible_singing_bowl`、`meditation_or_yoga_setup` | long_tail_trigger | 6～20 s | 场景锚点只作弱推断；去除突兀敲击，仅保留平滑长共振 |
| 66 | `wind_chime_bronze` | `bronze_temple_chime_or_bianzhong` | long_tail_trigger | 4～15 s | 使用低沉铜制共振，不用高频小铃 |

### 4.3 最小闭环与正式MVP的区别

- 最小闭环：66类各1份，合计66份；用于验证映射、格式和播放端，不适合长时间正式播放。
- 正式MVP：循环类至少2份，触发和长共振类至少3份，纹理类至少2～3份；预计约170～200份。
- 变体必须独立录制或具有真实不同事件，不能复制后只改速度、音高、音量或文件名。
- 个别高风险类别可以保留在受控词表中，但默认概率为0或要求用户开启；素材存在不等于必须播放。

以下类别尤其需要谨慎：

- `crowd_murmur`、`radio_static`、`tv_static`：不能含可辨识语言、节目或音乐。
- `distant_thunder`、`distant_bell`、`singing_bowl`、`wind_chime`、`wind_chime_bronze`：使用极长随机间隔并限制起音峰值。
- `bee_buzz`、`clock_tick`、`mouse_click`：容易造成紧张或烦躁，默认低概率或可关闭。
- `train_rumble`、`ocean_waves`、`blizzard_wind`：作为宽频持续层时，不与同类场景环境床重复叠加。

## 5. 环境音统一格式要求

### 5.1 母版格式

| 项目 | 强制或推荐要求 |
|---|---|
| 文件格式 | WAV，PCM，无损 |
| 采样率 | 48,000 Hz |
| 位深 | 24-bit；原始设备只有16-bit时可保留真实16-bit，不伪造动态范围 |
| 声道 | 优先原生立体声；单点稳定设备声可单声道 |
| 时长 | 推荐60～120秒；最低30秒 |
| 循环 | 必须实际试听验证；记录循环点和推荐交叉淡化时长 |
| 响度整理 | 初始目标约 -24 LUFS-I，允许约 ±2 LU；必须保存实测值 |
| 真峰值 | 建议不高于 -2 dBTP，不得削波 |
| 动态 | 稳定、低动态；不得出现突然近声、巨浪、雷击、鸣笛或门响 |
| 频谱 | 避免持续尖锐高频、过量超低频和明显电流啸叫 |
| 对话 | 不得包含可辨识句子、姓名或个人信息 |
| 头尾 | 清除无意义静音、操作声、直流偏置和咔哒声 |

### 5.2 立体声与双耳播放

- 环境床可以使用XY、ORTF或双麦克风立体声录制，以获得自然宽度。
- 不要直接使用带强烈头部转动痕迹的双耳实录作为通用环境床，否则会与前端HRTF重复空间化。
- 环境层以宽、稳定、接近中央的声场播放；单个实体的位置由单声道触发素材和HRTF处理。
- 立体声环境素材必须检查左右平衡、单声道兼容性及循环接缝。

### 5.3 Web交付格式

母版始终保留WAV。前端分发可额外生成：

| 用途 | 推荐交付格式 |
|---|---|
| Web环境音 | Opus，48 kHz，立体声约96～160 kbps |
| 移动端兼容备选 | AAC-LC，48 kHz，立体声约128～192 kbps |
| 本地高质量包 | FLAC或原始WAV |

MP3不得作为唯一母版。所有有损转码都应从无损母版生成，并分别试听循环接缝。

## 6. 视觉锚点关联声音统一格式要求

| 项目 | 强制或推荐要求 |
|---|---|
| 文件格式 | WAV PCM无损母版 |
| 采样率 | 48,000 Hz |
| 位深 | 24-bit；真实16-bit来源可保留16-bit |
| 声道 | 点声源触发和局部纹理优先单声道，便于HRTF定位；雨、海浪、风等宽环境循环可使用原生立体声 |
| 时长 | loop 30～120秒；texture 8～30秒；trigger 0.3～8秒；long_tail_trigger 5～20秒 |
| 变体 | 最小闭环每类1份；正式MVP中loop至少2份、texture至少2～3份、trigger和long_tail_trigger至少3份 |
| 响度 | 按主观听感统一，不只按峰值归一化；保存短时响度或事件响度测量 |
| 真峰值 | 建议不高于 -3 dBTP，保留HRTF与混音余量 |
| 头尾 | 事件前保留约10～50 ms自然起音余量，尾部保留完整衰减；删除多余静音和操作声 |
| 淡化 | 必要时使用5～30 ms短淡化防咔哒，但不得削掉真实起音 |
| 背景 | 尽量干声、少混响、低环境底噪，方便后续距离和房间处理 |
| 安全 | 不得包含爆音、尖叫、警报、鸣笛、强金属撞击或突然近距离峰值 |

### 6.1 哪些素材应录成单声道

HRTF播放端需要一个可定位的点声源。鸟鸣、翻页、杯碰、脚步、远雷、钟声等局部声源，以及键盘、书写等可定位纹理，应优先使用单支心形或超心形麦克风录制干声，再由播放端生成左右耳差异、距离衰减和混响。

雨、海浪、溪流、森林风叶、交通轰鸣等覆盖大范围画面的声音可以使用原生立体声，并作为宽环境床播放。不得把带有固定头部方向的双耳实录再次送入HRTF，也不得把宽环境床绑定到单个小框。

### 6.2 变体质量

同类多个变体需要满足：

- 语义相同但细节不同；
- 响度接近，试听切换时无明显跳变；
- 起音与尾音长度相近或在Manifest中记录；
- 不通过简单变速、变调复制来凑数量；
- `shuffle_no_repeat` 调度下连续播放不易被识别为重复。

### 6.3 推荐响度与播放音量

必须区分两个概念：

1. **素材响度**：音频文件自身的测量结果，用于让素材库内部具备一致基准；
2. **播放增益 `gain_db`**：播放计划叠加在素材上的相对增益，用于决定它在最终混音中的位置。

播放增益只有在素材已按统一响度基准整理后才有可比性。以下数值是助眠混音的初始推荐范围，必须通过整套混音试听校准，不代表扬声器或耳机的绝对声压级。

| 素材角色 | 素材整理建议 | 推荐 `gain_db` | 说明 |
|---|---|---:|---|
| 主场景环境床 | 约 -24 LUFS-I，真峰值不高于 -2 dBTP | -22～-16 dB | 最主要的连续背景；通常只启用一个 |
| 次场景环境床 | 同主环境床 | -30～-22 dB | 必须明显低于主环境，不与同族声音重复 |
| 锚点触发的宽环境循环 | 约 -24 LUFS-I | -30～-20 dB | 如雨、海浪、交通轰鸣；若已由场景层覆盖则不再叠加 |
| 间歇纹理 | 建议记录 LUFS-S max，真峰值不高于 -3 dBTP | -34～-24 dB | 如键盘、书写、猫呼噜、煨水 |
| 普通随机触发 | 按主观事件响度统一，真峰值不高于 -3 dBTP | -36～-26 dB | 如鸟鸣、翻页、脚步、纸张 |
| 谨慎型触发 | 同普通触发，但保留更多峰值余量 | -40～-32 dB | 如鼠标、杯碰、蜂鸣、风铃；默认概率更低 |
| 长共振触发 | 保存完整衰减尾部，真峰值不高于 -4 dBTP | -38～-28 dB | 如远雷、远钟、颂钵、铜铃；极长间隔 |
| 合成底噪 | 程序生成并在总线测量 | -42～-34 dB | 只作兜底或填充，不因存在空位自动添加 |
| Master总线 | 整体试听校准 | -4～-2 dB | 限幅阈值建议 -1 dBTP，保留叠加余量 |

按风险再做以下修正，修正后仍须落在安全范围内：

- `sleep_safety=high`：使用角色默认范围；
- `sleep_safety=medium`：相对同角色默认值降低约1～3 dB；
- `sleep_safety=cautious`：相对同角色默认值降低约3～6 dB，并降低概率、延长间隔；
- `mood=calm`、`mysterious`、`melancholic`：整体再降低约1～2 dB；
- 夜间：触发层可再降低约1～2 dB，并减少高频；
- HRTF距离处理产生的衰减应在角色增益之后计算，距离修正建议限制在0至-7 dB；
- 多层同时激活时不得简单相加到范围上限，决策器必须执行总线余量预测和必要的自动衰减。

禁止把检测置信度、深度值或边界框面积直接换算成音量。它们只参与候选门控、空间位置和受限制的距离修饰。

## 7. 文件命名与目录

```text
audio/
  ambient/
    natural/open_nature_wind_01.wav
    water/ocean_coast_bed_01.wav
  trigger/
    animal/bird_chirp_01.wav
    object/cup_clink_01.wav
  derived/
    opus/
  manifests/
    audio_manifest.json
  licenses/
    SOURCES.csv
    LICENSES/
```

命名格式：

```text
<sound_id>_<two_digit_variant>.wav
```

`asset_id` 建议：

```text
amb_<sound_id>_<variant>
trg_<sound_id>_<variant>
```

文件名和 `sound_id` 使用小写蛇形命名，不含空格、中文、设备名、作者名或未经控制的新类别。

## 8. 每份素材必须记录的元数据

```json
{
  "asset_id": "trg_bird_chirp_01",
  "sound_id": "bird_chirp",
  "role": "trigger",
  "path": "trigger/animal/bird_chirp_01.wav",
  "duration_s": 2.4,
  "loop": {
    "enabled": false,
    "seamless_verified": false,
    "crossfade_ms": 0
  },
  "audio": {
    "sample_rate_hz": 48000,
    "bit_depth": 24,
    "channels": 1,
    "lufs_i": null,
    "lufs_s_max": -27.2,
    "true_peak_db": -4.1
  },
  "capture": {
    "method": "self_recorded_field",
    "recorder": "example_recorder",
    "microphone": "example_microphone",
    "recorded_at": "2026-08-13",
    "location_precision": "city_only",
    "processing": [
      "high_pass_40_hz",
      "manual_declick",
      "trim"
    ]
  },
  "tags": {
    "sleep_safety": "high",
    "distance_character": "dry_near",
    "time_fit": ["morning", "afternoon", "dusk"]
  },
  "license": {
    "spdx": "LicenseRef-Project-Owned",
    "source_url": null,
    "author": "project_recording_team",
    "attribution_required": false,
    "redistribution_allowed": true,
    "ai_training_allowed": null
  },
  "sha256": "replace_with_real_checksum"
}
```

所有外部素材必须保存原始下载文件、来源页面快照或许可文本、下载日期、作者、许可证和校验值。授权无法确认时不得进入正式Manifest。

## 9. 现实可行的两种素材来源

本项目只采用以下两种来源。其他委托录音、场地合作、专业制作团队和线下采购方案不列入实施范围。

### 9.1 来源一：从网上公开素材库获取

适合难以自行录制的海浪、森林、动物、雷雨、飞机舱、火车、湿地和大型公共空间等声音。

#### 下载筛选顺序

1. 先按66个受控 `sound_id` 搜索，不按自由文本临时扩充声音类别。
2. 优先选择CC0或公共领域素材。
3. 其次选择允许商业使用和修改、且项目能够履行署名要求的CC BY素材。
4. 排除仅限非商业使用、禁止修改、来源不明或无法确认授权的素材。
5. 下载后保留原始文件，不直接覆盖；从原始文件制作标准WAV母版。
6. 对声音内容、底噪、对话、音乐、循环能力、响度和峰值逐项试听。

#### 可使用的公开渠道

- [Freesound许可说明](https://freesound.org/help/faq/)显示其素材可能分别采用CC0、CC BY或CC BY-NC，因此必须逐条检查。商业用途优先CC0或可正确署名的CC BY，排除CC BY-NC。
- [Wikimedia Commons复用说明](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)说明不同文件可能使用不同许可证，且仍可能涉及人格权等额外限制；不能把整个平台视为统一授权。
- [Pixabay内容许可摘要](https://pixabay.com/service/license-summary/)允许使用和修改内容，但限制将内容以独立素材形式销售或分发。如果产品会把原始WAV暴露给用户、放入SDK或公开素材包，需要额外谨慎。
- [Sonniss GDC Bundle许可](https://sonniss.com/gdc-bundle-license/)允许在媒体项目中使用和修改声音，但限制原样转售，并明确限制AI训练。可以作为嵌入应用播放的候选，不能自动视为允许发布独立原始素材。
- [Creative Commons许可证说明](https://creativecommons.org/share-your-work/use-remix/cc-licenses/)用于核对CC0、BY、NC、ND和SA等条件；需要剪辑、降噪和循环加工的素材应避免ND。

每份下载素材至少记录：

```text
source_url
downloaded_at
author
license_name
license_url_or_saved_text
attribution_text
commercial_use_allowed
modification_allowed
raw_redistribution_allowed
original_filename
original_sha256
```

公开可下载不等于可以商用或随产品再分发。用户上传平台也可能存在错误授权标签；授权不明确时不进入正式Manifest。

以下网络来源不得直接作为正式素材：

- 视频网站、社交媒体、电影、电视剧、游戏或音乐的截取音轨；
- 来源不明的网盘和“免费音效”聚合站；
- 只有试听页但没有明确许可证的文件；
- 仅限个人、教育、研究或非商业用途的素材；
- 含可辨识语言、音乐、广播或个人信息的环境录音。

### 9.2 来源二：线下人工录制

人工录制可以直接使用手机、平板、便携录音机或其他现有设备。设备常见输出为M4A/AAC、MP3、3GP、CAF或WAV；不要求录制设备直接生成标准WAV，后续统一转换即可。

最适合自行录制：

```text
键盘、鼠标、翻页、纸张、铅笔、钢笔、书本、时钟、风扇、
水壶、杯子、餐具、门、布料、扫地、烹饪、脚步、踩雪声
```

#### 最低录制要求

- 保留手机生成的原始文件，禁止直接覆盖或只保留处理后文件。
- 尽量关闭语音增强、自动美化、强降噪和其他通话优化功能；设备无法关闭时，在元数据中记录。
- 将手机调为飞行模式，避免通知、振动和无线电干扰。
- 触发音建议在较安静空间录制，设备距离声源约20～80厘米；先试录，避免输入削波。
- 每个动作连续录制10～20次，后续选择至少3个自然变体。
- 环境声连续录制至少3～10分钟，再截取稳定的30～120秒。
- 开始正式动作前先录约10～30秒现场底噪，帮助判断环境噪声和后期处理强度。
- 公共环境录音应避开可辨识对话、广播、音乐、姓名和个人信息。
- 不追求一次录成标准格式；录到干净、无削波、无无关声音的内容比文件扩展名更重要。

### 9.3 常见格式转换为标准WAV

标准处理母版统一为：

```text
容器：WAV
编码：PCM
采样率：48,000 Hz
位深：24-bit优先，真实16-bit来源也可保留为16-bit
声道：局部点声源优先单声道；宽环境声保留立体声
```

转换只能改变容器、采样率、位深和声道，不能恢复M4A、MP3等有损文件已经丢失的细节。必须在Manifest中保留原始格式和编码信息。

#### 方法一：FFmpeg命令行

M4A、AAC、MP3、OGG、FLAC、WMA、3GP和多数CAF文件都可以用同一命令结构转换。

局部点声源转成48 kHz、24-bit、单声道WAV：

```powershell
ffmpeg -i "input.m4a" -vn -ar 48000 -ac 1 -c:a pcm_s24le "output.wav"
```

适用于踩雪、脚步、翻页、杯碰、鸟鸣、键盘等需要HRTF定位的声音。

宽环境声保留立体声：

```powershell
ffmpeg -i "input.m4a" -vn -ar 48000 -ac 2 -c:a pcm_s24le "output.wav"
```

适用于海浪、雨、森林、交通轰鸣和公共环境声。原始文件本身只有单声道时，不应为了凑成立体声而复制或伪造空间信息。

保留输入声道数量，只统一采样率和PCM编码：

```powershell
ffmpeg -i "input.m4a" -vn -ar 48000 -c:a pcm_s24le "output.wav"
```

真实低精度来源需要输出16-bit时：

```powershell
ffmpeg -i "input.m4a" -vn -ar 48000 -ac 1 -c:a pcm_s16le "output.wav"
```

批量转换当前目录中的M4A为单声道WAV：

```powershell
Get-ChildItem -LiteralPath . -Filter *.m4a | ForEach-Object {
  $out = Join-Path $_.DirectoryName ($_.BaseName + '.wav')
  ffmpeg -i $_.FullName -vn -ar 48000 -ac 1 -c:a pcm_s24le $out
}
```

批量转换前应先复制原始文件到只读归档目录，并确认输出目录中没有同名WAV，避免覆盖已有人工剪辑结果。

查看输入文件的真实编码、采样率和声道：

```powershell
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bits_per_sample -of default=noprint_wrappers=1 "input.m4a"
```

#### 方法二：Audacity图形界面

适合需要同时剪辑、拆分多次动作、淡入淡出和人工试听的文件。

1. 安装Audacity；如M4A不能导入，按软件提示安装其FFmpeg组件。
2. 打开M4A、MP3、FLAC或其他原始音频。
3. 先保存Audacity工程或保留原始文件副本。
4. 剪除开始/结束录制操作声、说话和无关段落。
5. 将一次长录音拆成多个真实变体，例如 `snow_crunch_01`、`02`、`03`。
6. 对局部点声源混合为Mono；宽环境声保留Stereo。
7. 在导出窗口选择WAV，采样率设为48,000 Hz，编码选择Signed 24-bit PCM；若设备或版本只方便导出16-bit，可先使用Signed 16-bit PCM。
8. 导出后重新打开并试听头尾、峰值、声道和内容。

[Audacity WAV导出说明](https://manual.audacityteam.org/man/wav_export_options.html)支持选择Mono或Stereo、采样率和PCM编码；其[导出说明](https://manual.audacityteam.org/man/file_export_dialog.html)也说明M4A导入可能需要FFmpeg组件。

#### 不推荐：在线格式转换网站

在线转换可能压缩音频、改变声道、限制长度，且需要上传未发布的原始录音。除临时测试外不使用；正式素材采用本地FFmpeg或Audacity转换。

### 9.4 转换后的最低验收

每个转换结果至少检查：

- 文件能完整解码和播放；
- 采样率为48 kHz，PCM位深与记录一致；
- 局部声源为单声道，宽环境声声道没有被错误改变；
- 无削波、数字咔哒、明显突发噪声和无关对话；
- 头尾保留自然起音与衰减；
- 原始文件、转换后文件和处理过程均有记录；
- 只有完成剪辑、试听和命名后，文件才写入正式 `audio_manifest.json`。

## 10. 分类采集方案

### 10.1 室内拟音日

一次安静室内录制可完成66类中的约20～25个室内声音类别，并为高频类别录制多个变体：

```text
键盘、鼠标、翻页、纸张、铅笔/钢笔书写、时钟、风扇、
热水壶、杯子、餐具、门、布料、软脚步
```

每类录10～20次，改变动作细节而不改变声音语义。避免同时更换房间、麦克风距离和物体材质，否则同类响度及空间特征难以统一。

### 10.2 户外自然录音

建议清晨和夜间分别录制：

- 清晨：开阔自然风、森林、远鸟、乡村底景；
- 傍晚或夜间：湿地、蟋蟀、蛙鸣；
- 海岸：选择中等稳定潮汐，远离游客、道路和强风；
- 雨声：优先在可控屋檐、窗户或安静庭院录制，另录无雨室内底噪。

自然环境至少连续录制5～10分钟，再筛选稳定的60～120秒片段。不要只录恰好一分钟，否则难以避开突发噪声和制作循环。

### 10.3 公共空间录音

咖啡馆、商场、交通和动物设施需要：

- 获得场地方许可；
- 避开可辨识对话、广播、音乐、商标提示音和个人信息；
- 使用较远、扩散的环境声，不将单个人作为录音主体；
- 无法去除版权音乐或广播时放弃该录音；
- 保留录音日期、许可联系人和授权范围。

### 10.4 难采或高风险声音的替代方案

| 目标 | 不推荐直接采集 | 建议替代 |
|---|---|---|
| 雷暴 | 近距离真实雷击，危险且峰值不可控 | 从公开素材库筛选明确授权的远雷；没有合格素材时暂不提供 |
| 动物 | 逼近野生动物或录制高刺激叫声 | 从公开素材库筛选明确授权、距离合适且低刺激的动物声音 |
| 火车/飞机舱 | 录入广播、音乐和乘客对话 | 优先使用公开素材库；自行乘坐时只能录无广播、无可辨识对话的稳定片段 |
| 火焰 | 大型篝火近距离录制 | 人工录制小型可控火源并保证防火；否则使用公开素材库 |
| 城市交通 | 路边近距离录制鸣笛和急刹 | 人工在安全且较远的位置录稳定底景，或使用公开素材库 |
| 海浪 | 强风和贴近浪头录制 | 人工在中等安全距离、背风位置长时间录制，或使用公开素材库 |

## 11. 后期处理流程

```text
原始录音只读归档
  → 选择片段
  → 去直流与人工去咔哒
  → 极轻降噪或不降噪
  → 必要的低切与风险频段控制
  → 剪辑、淡化、循环处理
  → 响度与真峰值测量
  → 导出48 kHz/24-bit WAV母版
  → 耳机、扬声器、单声道兼容试听
  → Manifest、许可证与SHA-256登记
  → 从母版生成Web派生格式
```

处理原则：

- 不追求“完全无噪”，过度降噪会产生水声和金属伪影。
- 不用重压缩器把环境声压成恒定响度。
- 不对短触发音只做峰值归一化；必须统一主观事件响度。
- HRTF触发素材尽量保持干声，不预先添加明显空间混响。
- 环境循环至少在耳机上连续播放5分钟检查接缝。

## 12. 验收标准

### 12.1 文件与元数据

- [ ] 所有母版为48 kHz WAV PCM，位深真实可追溯。
- [ ] 每个 `asset_id` 唯一并可从Manifest解析。
- [ ] 每份素材有来源、作者、许可、下载或录制日期和SHA-256。
- [ ] 外部素材的许可允许目标产品用途、修改和所需分发方式。
- [ ] 环境层循环信息经过实际验证，不只写元数据声明。

### 12.2 音频质量

- [ ] 无削波、直流偏置、头尾咔哒、意外操作声和明显左右失衡。
- [ ] 无可辨识对话、音乐、广播、鸣笛、警报、尖叫和突然爆裂。
- [ ] 环境音连续试听无明显循环接缝和高频疲劳。
- [ ] 同一触发类别的三个变体响度一致且内容不机械重复。
- [ ] 触发音通过单声道、HRTF双耳和整套混音试听。

### 12.3 覆盖率

- [ ] 20份环境母版均能映射到受控场景，`none`安全回退为静音。
- [ ] `reference_sound_id` 的66个类别均有至少一份合法素材，或在发布元数据中明确标记为尚未就绪且禁止生成播放引用。
- [ ] 正式MVP中loop至少2个变体、texture至少2～3个变体、trigger和long_tail_trigger至少3个变体。
- [ ] 视觉锚点均来自2.3具体词表，并能通过 `anchor_sound_mapping_reference` 解析到受控 `sound_id`。
- [ ] 场景环境床与视觉锚点关联的宽频循环音执行声音家族去重，不重复叠加海浪、雨、交通或风声。
- [ ] 不存在未经词表登记的临时声音类别。

## 13. 推荐实施顺序

1. 以视觉规范2.3中的66项 `reference_sound_id` 和 `anchor_sound_mapping_reference` 冻结两份正式配置：`scene_audio_profiles.json`、`trigger_anchor_sound_map.json`。
2. 用一次室内拟音日覆盖约20～25类声音，并优先为随机触发类录满3个变体。
3. 分清晨、夜间、海岸和雨天进行4组长时环境采集。
4. 对难以人工录制的声音，从公开素材库逐条核验授权后补齐。
5. 建立Manifest、许可证档案和自动技术检测。
6. 先完成10～20份场景环境音和66类锚点关联声音的最小覆盖，再按角色补足正式MVP变体并完成耳机试听。
7. 根据真实视觉数据中的场景和锚点频率决定下一批下载或录制任务，不按词表顺序平均扩充。

最重要的修正原则是：**词表限制声音语义，真实数据分布决定下载与录制优先级，变体数量保证播放不机械，许可证和Manifest保证素材真正可交付。**
