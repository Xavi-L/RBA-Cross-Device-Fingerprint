# App参与双端检测的覆盖与剩余证据

本表按原App成员的实际raw引用定向检查其backend文件目录，并用完整App session精确匹配已知P2与60条双端索引。
原378条及180条专项引用的12个backend目录均没有独立Browser raw或配对provenance文件，且在已知配对索引中无相同App session。
因此这些已保存成员不能做同阶段双端比较；这不是根据“旧实验”名称推断，也不是断言全仓不存在其他未索引材料。MTC正常配对不能填补受控攻击的Browser缺项。

|材料|App位置|同阶段Browser|完整配对|完整三阶段组|正常|有效干预|
|---|---:|---:|---:|---:|---:|---:|
|controlled / w10-cdp-emulation-screen-metrics-only-v1|27|0|0|0|18|9|
|controlled / w10-cdp-emulation-timezone-only-v1|27|0|0|0|18|9|
|controlled / w6-tool-054-legacy-default-v1|27|0|0|0|18|9|
|controlled / w6-tool-055-legacy-default-v1|27|0|0|0|18|9|
|controlled / w6-tool-056-legacy-default-v1|27|0|0|0|18|9|
|controlled / w6-tool-058-legacy-default-v1|27|0|0|0|18|9|
|controlled / w9-rule-boundary-cdp-platform-only-v1|27|0|0|0|18|9|
|controlled / w9-rule-boundary-cdp-resource-pair-v1|27|0|0|0|18|9|
|controlled / w9-rule-boundary-cdp-ua-only-v1|27|0|0|0|18|9|
|controlled / w9-rule-boundary-cdp-ua-platform-desktop-v1|27|0|0|0|18|9|
|controlled / w9-rule-boundary-cdp-webdriver-only-v1|27|0|0|0|18|9|
|controlled / w9-stealth-boundary-languages-only-v1|27|0|0|0|18|9|
|controlled / w9-stealth-boundary-plugins-mime-v1|27|0|0|0|18|9|
|controlled / w9-stealth-boundary-webgl-pair-v1|27|0|0|0|18|9|
|memory / memory_16GiB|18|0|0|0|12|6|
|memory / memory_2GiB|18|0|0|0|12|0|
|memory / memory_4GiB|18|0|0|0|12|6|
|memory / memory_8GiB|18|0|0|0|12|6|
|timezone / A_America/Los_Angeles|9|0|0|0|6|3|
|timezone / A_UTC|9|0|0|0|6|3|
|timezone / L_America/Los_Angeles|9|0|0|0|9|0|
|timezone / L_UTC|9|0|0|0|9|0|
|screen / A_screen|18|0|0|0|12|6|
|screen / L1_screen|18|0|0|0|18|0|
|screen / L2_screen|18|0|0|0|18|0|
|screen / L3_screen|18|0|0|0|18|0|
|paired60 / A_APP_LANG|6|6|6|2|4|2|
|paired60 / A_APP_TZ|6|6|6|2|4|2|
|paired60 / A_BROWSER_LANG|6|6|6|2|4|2|
|paired60 / A_BROWSER_TZ|6|6|6|2|4|2|
|paired60 / L_BROWSER_LANG|6|6|6|2|6|0|
|paired60 / L_SYS_LANG|6|6|6|2|6|0|
|paired60 / L_SYS_TZ|6|6|6|2|6|0|
|paired60 / language_fr|9|9|9|3|6|3|
|paired60 / timezone_tokyo|9|9|9|3|6|3|

逐位置的真实文件与物理行号见 [pairing_positions.jsonl](results/pairing_positions.jsonl)；机器表见 [CSV](PAIRED_COVERAGE.csv)。

## 三条证据线

- App单端／内部跨层：本轮378条主体与专项统一回放、四项重选消融、小树对照，见REPORT。
- App↔独立Browser语言／时区：既有18先导＋42匹配对照共60条，20组三阶段；4次App干预、10次Browser干预、46条正常。此前局部四视图与C1/C2实验保留。本轮只补App模型回放。
- 其他App攻击配置的跨端贡献：原App受控及内存／屏幕专项缺少同阶段Browser与完整配对；本轮不能声称其双端组件消融已完成。

## 最小下一轮：一个有针对性的配对补证批次（尚未授权采集）

优先只补 **w9-rule-boundary-cdp-resource-pair-v1＋memory_4GiB** 的真实App与独立Browser三阶段配对。前者覆盖旧CPU/内存联合修改，后者隔离App Web内存修改，最适合区分“App内部Native参照”与“未被修改的独立Browser参照”。先在一个已用环境、每配置3次重复完成同一组pre／change／post双端输入，并加匹配的无干预三阶段对照；无需重采378条。
要论证App作为参照端，再在同一批次安排与这些字段相对应的Browser侧单端修改，并验证实际变化。若Browser不提供有效内存观测，保留U/无效尝试，不用另一端数值补齐。
本方案缺的首先是上述阶段的真实配对输入；配对齐备后还需单独冻结可适用的跨端候选与同成员方法对照。当前C1/C2只覆盖语言/时区，不能直接代表资源跨端方法。
UA、屏幕、webdriver、WebGL及其余工具配置仍在覆盖表中保留缺项。若论文要对它们作跨端有效性主张，需要相应后续证据；最小资源批次不自动关闭这些缺口。
