## English Abstract

To the best of our knowledge, we propose the first theoretical framework for three-way mutual verification of mobile device fingerprints across the native system, the WebView host, and web content. Rather than trusting any single source, the framework checks whether observations from the same device are mutually compatible. Its central idea is to identify contradictions introduced by fingerprint manipulation while allowing differences that arise from normal operation.

We develop HybridGuard to investigate this framework, building tools for fingerprint collection, controlled manipulation, and experimental evaluation. We assemble 891 records from normal Android devices and conduct controlled experiments covering 14 manipulation configurations. Using these data, we develop detection methods and compact models that examine both individual reports and relationships between observations. We also evaluate legitimate changes in device settings to assess whether the methods distinguish normal behavior from manipulation.

Our experiments show that mutual verification can reveal manipulations missed by checking individual reports alone and avoid false alarms for legitimate system changes. In the main controlled experiment, HybridGuard detects 105 of 126 manipulated samples, achieving an 83.3% detection rate with no false alarms among 252 normal samples. Targeted experiments demonstrate complementary benefits: relationships between observations expose otherwise undetected modifications and prevent normal changes from being mistaken for manipulation. These findings support mutual verification as an effective approach to detecting fingerprint manipulation while controlling false alarms.

## 中文参考版

据我们所知，本文首次提出面向移动设备指纹的三端互证理论框架，通过原生系统、WebView 容器与网页之间的相互参照，检验设备指纹的可信性。该框架不将任何单一来源视为可信依据，而是检查同一设备上的不同观测是否相互兼容。其核心思想是在允许正常运行产生合理差异的前提下，识别指纹操纵引入的矛盾。

为研究这一框架，我们构建了 HybridGuard，开发了指纹采集、受控操纵与实验评估工具，整理了来自正常 Android 设备的 891 条记录，并开展了覆盖 14 种操纵配置的受控实验。在此基础上，我们设计了检测方法与紧凑模型，同时考察单份报告及不同观测之间的关系。此外，我们对设备设置的正常变化进行评估，以检验方法能否区分正常行为与指纹操纵。

实验表明，相互参照能够发现仅检查单份报告时遗漏的操纵，并避免对正常系统变化产生误报。在受控主实验中，HybridGuard 检出了 126 个操纵样本中的 105 个，检出率为 83.3%，且在 252 个正常样本上未产生误报。专项实验进一步展示了观测间关系的双重作用：既能揭示原本未被检出的修改，也能避免将正常变化误判为操纵。这些结果支持将相互验证作为一种兼顾指纹操纵检测与误报控制的有效方法。

------

**措辞边界：**“零误报”限定于上述受控主实验，仓库中的其他真机及专项实验并非全部零误报，不能扩写成“所有正常设备均不误报”。“首次”保留了 *To the best of our knowledge*，正式投稿前仍需由相关工作综述支撑。