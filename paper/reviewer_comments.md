Contribution Details
----------------------------------------
ID: 1957
Title: Integrating Multi-View Stereo and Depth Foundation Models for Precise 3D Reconstruction of Thin Urban Structures


Review Result of the Program Committee: This contribution has been accepted and will be published in the 2026 proceedings.
Your paper will be published in the ISPRS Archives of the Photogrammetry, Remote Sensing and Spatial Information Sciences (https://www.isprs.org/publications/archives.aspx), subject to the final camera-ready version.

One of the co-authors has to be registered to the 2026 ISPRS Congress for final publication of your paper.


Overview of Reviews
----------------------------------------

Review 1
========

Contribution of the Submission
------------------------------
Proposes a hybrid depth reconstruction pipeline that combines metric MVS depth with monocular depth foundation models to accurately reconstruct thin urban structures such as power lines.


Evaluation of the Contribution
------------------------------
*Innovation                (15%): 4
Scientific formulation     (10%): 6
Experiments and validation (15%): 6
Relevance                  (10%): 6
Quality of Presentation    (10%): 6
Overall Recommendation     (40%): 6
Total points (out of 100)       : 57


Comments for the authors
------------------------
- The main strength of the work lies in its practical relevance for urban Digital Twin applications and its clear demonstration on challenging real-world UAV imagery. The integration of MVS priors into foundation models is a sensible and effective strategy.

- However, the evaluation is largely qualitative, and the lack of quantitative metrics limits the ability to objectively assess performance gains. In addition, the novelty is primarily in system integration rather than in methodological innovation. The approach is currently validated on a narrow object category (power lines), which raises questions about generalizability.

- To improve the work, the authors could include quantitative evaluations, broader object classes, and comparisons with additional baselines. A clearer discussion of limitations and scalability would further strengthen the contribution.

 


-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-


Review 2
========

Contribution of the Submission
------------------------------
The submission presents a two-stage depth/reconstruction pipeline aimed at thin, low-texture urban structures (power lines). It anchors a monocular depth foundation model with sparse, metric MVS depth/points to recover absolute scale, then applies a fine refinement using depth edges/contours and clustering to stabilize thin-object depth against background “pull.” Qualitative comparisons suggest improved continuity/cleanliness for wires compared to MVS-only and monocular-only depth.


Evaluation of the Contribution
------------------------------
*Innovation                (15%): 6
Scientific formulation     (10%): 6
Experiments and validation (15%): 4
Relevance                  (10%): 8
Quality of Presentation    (10%): 6
Overall Recommendation     (40%): 6
Total points (out of 100)       : 59


Comments for the authors
------------------------
Strengths:
1. Relevant, real-world problem: thin structures (power lines) are a known failure case for standard MVS/photogrammetry and for learned depth priors.
2. Practical hybrid idea: using metric sparse MVS information to anchor scale in monocular depth is aligned with mapping needs (metric consistency)

Weakness:
1. Limited evidence: claims rely mainly on qualitative visuals; there are no quantitative metrics, ablations, or robustness checks described.
2. The abstract explicitly references an existing “prior depth anchoring” approach; it is unclear what is new beyond combining known components and adding post-processing.
3. key implementation/algorithmic details are missing (e.g., how priors constrain depth—loss vs conditioning; how contours are extracted/filtered; clustering choice; how thin-object pixels are identified without GT).

Suggestions:
1. Include ablations: (a) mono-depth only, (b) MVS only, (c) anchored mono-depth (coarse), (d) + refinement (fine). This is crucial to show where gains come from.
2. Add quantitative evaluation
3. Detail the refinement step: how edges/contours are used, how clusters are formed, what statistic replaces depths, and why this preserves geometry (and doesn’t oversmooth or hallucinate).

 


-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-


Review 3
========

Contribution of the Submission
------------------------------
This submission addresses image-based 3D reconstruction for an urban scenario with thin structures. The main contribution consists in the combination of Multi-View Stereo (MVS) and depth foundation models. The expected benefit relies on combining the metric accuracy of sparse MVS data with the dense structural coherence of monocular foundation models.


Evaluation of the Contribution
------------------------------
*Innovation                (15%): 8
Scientific formulation     (10%): 8
Experiments and validation (15%): 6
Relevance                  (10%): 8
Quality of Presentation    (10%): 6
Overall Recommendation     (40%): 7
Total points (out of 100)       : 71


Comments for the authors
------------------------
1) Innovation:
*Novelty is fair; related work is sufficiently discussed to see the addressed research gap.
*The applied methodology is sufficiently described.
*The proposed principle for integration of Multi-View Stereo (MVS) and depth foundation models is technically sound.

2) Scientific Formulation:
*The Extended Abstract is informative and contains all required information.
*Research questions are clear.
*The proposed contributions seem appropriate to achieve improved results.
*Claims are supported by the depicted first results.

3) Experiments and Validation:
*Performance is evaluated for drone-captured imagery of an urban scenario with complex power line networks. Further description of the used dataset would have been important.
*Performance evaluation involves a comparison to other techniques (MVS Depth, Mono Depth, Coarse Depth).
*Only qualitative results are provided.
*Results of the proposed approach seem promising, yet visualizations in Figure 1 are hard to assess.
*Limitations are addressed.

4) Relevance:
*The addressed topic is highly relevant for the event.
*There is a methodological and an application-oriented contribution in this Extended Abstract.

5) Quality of Presentation:
*The Extended Abstract is well-structured and well-written. Explanations are sound and clear. Visualizations are informative, yet zoom-ins might be required to better allow visually assessing the differences between achieved results.
*Discussion of related work is adequate, thus significance of the presented work is fair.