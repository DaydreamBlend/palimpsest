# Test_Paper — source I 길이와 입력 묶음

문자 수는 Unicode codepoint, 단어 수는 공백 기준이다. 모델 token 수와 이미지 비용은 측정하지 않았다.
원문 I229개를 재작성하지 않은 조회 시안이며 자동 절 검출·embedding·I2K 실행 결과가 아니다.

| 대상 | I 수 | 중앙 문자 | 평균 문자 | P90 문자 | 최대 문자 | 중앙 단어 |
|---|---:|---:|---:|---:|---:|---:|
| all | 229 | 33 | 275.24 | 904 | 3906 | 4 |
| text | 193 | 39 | 271.16 | 844 | 3906 | 4 |
| image_text_only | 36 | 2.0 | 297.14 | 1641 | 2737 | 1.0 |
| article_text | 41 | 672 | 914.34 | 2026 | 2697 | 102 |

article_text는 초록 이후 Text 중 키워드·별도 caption continuation2개를 제외한41개다. 후반 설명을 포함한다.
전체 Text193개에는 header33/footer28/page number14/title30과 초록 이전 metadata text42개가 포함된다.
Image의 문자 수는 픽셀이 아닌 caption·패널 라벨 등 textual content만 측정한 값이다.

## 검토된 입력 묶음

Abstract/Introduction은 각각 하나다. Results는 이 논문의 명시적 Figure 참조를 검토해 6묶음으로 구성했다. 
Figure1 묶음에는 원문 소절2개가 포함된다. 다른 논문의 다대다 Figure 관계를 한 그림에 강제 배정하는 규칙은 아니다.
Supplementary Figure는 별도 자료가 필요하다. 전체 페이지와 그림 연결에도 기존 proposal/uncertainty 상태를 유지한다.

| 묶음 | I 수 | 문자(구분자 포함) | 공백 단어 | 원본 페이지 |
|---|---:|---:|---:|---|
| Abstract | 1 | 1239 | 150 | 1 |
| Introduction | 4 | 2888 | 378 | 1, 2 |
| Results / Figure 1 (two source subsections) | 16 | 6420 | 955 | 2, 3 |
| Results / Figure 2 | 13 | 3539 | 512 | 2, 4, 5 |
| Results / Figure 3 | 8 | 4600 | 676 | 5, 6 |
| Results / Figure 4 | 3 | 4753 | 694 | 5, 7 |
| Results / Figure 5 | 5 | 5546 | 773 | 5, 8, 9, 10 |
| Results / Figure 6 | 15 | 4934 | 699 | 8, 11, 12 |
| Discussion | 7 | 4153 | 580 | 8, 10 |
| Online Methods / Mice | 3 | 816 | 114 | 10 |
| Online Methods / Efferocytosis | 3 | 2440 | 335 | 10, 12 |
| Online Methods / Animal Models and Treatments | 3 | 3122 | 512 | 12 |
| Online Methods / Cell Sorting, Culture, and Analysis | 3 | 3016 | 462 | 12, 13 |
| Online Methods / Human Cell Manipulation | 3 | 1956 | 283 | 13 |
| Online Methods / Statistical Analysis | 2 | 244 | 34 | 13 |
| Author contributions / Funding / Acknowledgments / Supplementary material | 8 | 1885 | 265 | 13 |
| References / disclosures | 6 | 7620 | 1029 | 14 |
| Retained front matter / keywords / page furniture | 126 | 4282 | 544 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 |

## 전체 I별 길이

| 페이지 | Information ID | kind / source type | 문자 | 공백 단어 |
|---:|---|---|---:|---:|
| 1 | `01a08a48-474f-767b-ae80-7e4ceecdf91a` | text / header | 1 | 1 |
| 1 | `01a08a48-4758-7dbc-b36b-f5f94da89b2e` | text / header | 9 | 1 |
| 1 | `01a08a48-4762-726c-a406-8e317cffd84b` | text / header | 13 | 2 |
| 1 | `01a08a48-476b-7ee0-80d9-aa4e9736e8a7` | text / header | 17 | 2 |
| 1 | `01a08a48-4775-7205-8258-14484fbb8453` | text / header | 27 | 4 |
| 1 | `01a08a48-477e-7708-9504-5cb904bb0f49` | text / header | 29 | 2 |
| 1 | `01a08a48-4787-7f3f-92c5-8b7343773c38` | text / header | 17 | 3 |
| 1 | `01a08a48-4530-710d-a1b6-03f3d0276b7f` | text / title | 11 | 2 |
| 1 | `01a08a48-453d-729e-888e-9fece4d70492` | text / title | 10 | 2 |
| 1 | `01a08a48-4547-7ebd-894a-ab8bc7da4e83` | text / text | 19 | 2 |
| 1 | `01a08a48-4551-7bd9-b466-17e4190ba439` | text / text | 34 | 4 |
| 1 | `01a08a48-455d-74d4-8996-9d6cc6099697` | text / title | 12 | 2 |
| 1 | `01a08a48-4567-750c-9bb4-03c5e94fe08a` | text / text | 21 | 3 |
| 1 | `01a08a48-4571-7dc0-8804-afc82ea5ef4a` | text / text | 37 | 5 |
| 1 | `01a08a48-457c-7951-93d0-c1fa626fc2c8` | text / text | 21 | 3 |
| 1 | `01a08a48-4587-75f0-b7e3-0dfd1aa7c7b3` | text / text | 36 | 5 |
| 1 | `01a08a48-4591-7292-b5a7-256dae8dcd10` | text / title | 16 | 1 |
| 1 | `01a08a48-459a-78c8-aae1-0c2a0baa368b` | text / text | 16 | 2 |
| 1 | `01a08a48-45a3-7f6f-998e-fb0e8a4a2543` | text / text | 26 | 1 |
| 1 | `01a08a48-45ae-72f7-83a1-0c3eb4d5fae2` | text / title | 22 | 3 |
| 1 | `01a08a48-45b7-791a-a05b-ce1dab83fe69` | text / text | 17 | 2 |
| 1 | `01a08a48-45c0-7e61-a095-18b4997819b6` | text / text | 27 | 3 |
| 1 | `01a08a48-45ca-7835-a2bf-31736806452d` | text / text | 32 | 5 |
| 1 | `01a08a48-45d3-7ddb-812e-118a4affd7be` | text / text | 37 | 4 |
| 1 | `01a08a48-45dd-7bdb-84bd-0335a8d2345b` | text / text | 17 | 3 |
| 1 | `01a08a48-45e8-75a4-88f6-78d0a0bf5cfc` | text / text | 15 | 2 |
| 1 | `01a08a48-45f3-7020-9da2-cb54bc940298` | text / text | 36 | 4 |
| 1 | `01a08a48-45fd-7136-bba7-a792fbbcbcfb` | text / text | 6 | 1 |
| 1 | `01a08a48-4607-7162-9b0a-b9bdc1d41daf` | text / text | 24 | 2 |
| 1 | `01a08a48-4611-7705-9cdd-44dafbe72847` | text / text | 32 | 3 |
| 1 | `01a08a48-461b-7057-a01a-5da474a0e31b` | text / text | 6 | 1 |
| 1 | `01a08a48-4625-7156-a4f6-7d5c92ecdf21` | text / text | 24 | 2 |
| 1 | `01a08a48-462e-75f1-94c5-12582ea972e7` | text / text | 33 | 4 |
| 1 | `01a08a48-4637-7ed5-8958-2b309cf5689e` | text / text | 37 | 4 |
| 1 | `01a08a48-4642-7bb1-9e68-c8f53e9ec92e` | text / title | 18 | 2 |
| 1 | `01a08a48-464c-714d-86b9-c96b1742bcd0` | text / text | 29 | 5 |
| 1 | `01a08a48-4657-70b6-b48b-b4aa9380329a` | text / text | 27 | 3 |
| 1 | `01a08a48-4661-7f28-8f9b-d2da6a29bd07` | text / text | 11 | 1 |
| 1 | `01a08a48-466b-7a03-9d7c-379a9d0dd595` | text / text | 24 | 5 |
| 1 | `01a08a48-4676-7509-a3dd-e0141d912e44` | text / text | 23 | 3 |
| 1 | `01a08a48-4680-7d75-bd9b-8e1497c958c5` | text / text | 21 | 4 |
| 1 | `01a08a48-468a-7442-838d-26f99fecf522` | text / text | 25 | 4 |
| 1 | `01a08a48-4693-7c70-966b-bf1fbe4b68ba` | text / text | 27 | 4 |
| 1 | `01a08a48-469c-7fae-9e58-91d9c4252508` | text / title | 9 | 1 |
| 1 | `01a08a48-46a7-77a8-be35-1a7f6e75af39` | text / text | 34 | 6 |
| 1 | `01a08a48-46b1-71d7-a55a-6487859ef73b` | text / text | 29 | 4 |
| 1 | `01a08a48-46bb-7c63-a23d-362ad0a69053` | text / text | 34 | 6 |
| 1 | `01a08a48-46c5-7bcf-8e2e-24f8e0d7e809` | text / text | 33 | 6 |
| 1 | `01a08a48-46cf-7033-aca6-e078009f3f77` | text / text | 31 | 4 |
| 1 | `01a08a48-46d9-71ff-a152-ff99db2cab94` | text / text | 27 | 3 |
| 1 | `01a08a48-46e2-7182-a0d8-cc306afce4b7` | text / text | 26 | 2 |
| 1 | `01a08a48-46ec-72bc-89f4-72054c62e2fb` | text / text | 32 | 4 |
| 1 | `01a08a48-46f6-761e-80c3-b55de6f066cd` | text / text | 37 | 4 |
| 1 | `01a08a48-4700-72de-9711-64345c414257` | text / text | 29 | 2 |
| 1 | `01a08a48-470a-7a88-90fa-70e387b870dc` | text / title | 132 | 14 |
| 1 | `01a08a48-4714-7d45-adbd-9a8a48309405` | text / text | 292 | 39 |
| 1 | `01a08a48-471e-750e-b336-5e42c002a996` | text / text | 293 | 30 |
| 1 | `01a08a48-4728-7503-b636-0fc40b9c27da` | text / text | 1239 | 150 |
| 1 | `01a08a48-4732-7033-bab9-9a21dbb475c4` | text / text | 116 | 11 |
| 1 | `01a08a48-473b-746b-a281-a5f3a6dd24a9` | text / title | 12 | 1 |
| 1 | `01a08a48-4745-75e0-b26b-be06b2faa509` | text / text | 645 | 88 |
| 1 | `01a08a48-4791-7c2f-af90-71388a7f758b` | text / footer | 45 | 5 |
| 1 | `01a08a48-479b-7049-8105-ec668761160a` | text / page_number | 1 | 1 |
| 1 | `01a08a48-47a4-76f5-9f83-1d46846a8e8d` | text / footer | 39 | 8 |
| 2 | `01a08a48-4810-7154-9ee5-6fdb3c5033e4` | text / header | 15 | 3 |
| 2 | `01a08a48-4819-78f5-ad1a-06263a1b35f8` | text / header | 42 | 4 |
| 2 | `01a08a48-47ae-7cd9-97d8-4a224753b241` | text / text | 905 | 114 |
| 2 | `01a08a48-47b8-7370-8bad-948831a5e89e` | text / text | 1320 | 175 |
| 2 | `01a08a48-47c2-7c26-b023-63288611697f` | text / title | 7 | 1 |
| 2 | `01a08a48-47cb-7e11-86d3-61780d801c8a` | text / title | 103 | 12 |
| 2 | `01a08a48-47d5-7b79-b21f-20f0bef4149e` | text / text | 785 | 113 |
| 2 | `01a08a48-47df-7854-ad33-8b47a21a5096` | text / text | 434 | 57 |
| 2 | `01a08a48-47e9-7001-a3b5-04aa70dcbdc4` | text / title | 55 | 6 |
| 2 | `01a08a48-47f3-7f02-aece-2405972f1277` | text / text | 2228 | 323 |
| 2 | `01a08a48-47fd-713e-a574-79b0878d5fe1` | text / title | 85 | 10 |
| 2 | `01a08a48-4806-76f4-82c1-4a4a0f0a3945` | text / text | 180 | 27 |
| 2 | `01a08a48-4822-7da1-a42d-4a5922203047` | text / footer | 45 | 5 |
| 2 | `01a08a48-482c-72dc-8515-ddfd4fe15eb1` | text / page_number | 1 | 1 |
| 2 | `01a08a48-4835-7823-9256-077bf49297f2` | text / footer | 39 | 8 |
| 3 | `01a08a48-48a0-7906-bb82-3f04d3fe06ae` | text / header | 15 | 3 |
| 3 | `01a08a48-48a9-7ae7-a3ca-abdce81d1a05` | text / header | 42 | 4 |
| 3 | `01a08a48-483f-78af-a20a-f86024eb07dc` | image / image | 4 | 2 |
| 3 | `01a08a48-4849-7372-9f98-dc627e00fa1f` | image / image | 0 | 0 |
| 3 | `01a08a48-4852-7856-b1be-2a5679502392` | image / image | 2 | 1 |
| 3 | `01a08a48-485c-714f-ae5e-69a136101e2a` | image / image | 25 | 4 |
| 3 | `01a08a48-4865-7984-9ff8-5b22feeaaeb4` | image / image | 2 | 1 |
| 3 | `01a08a48-486e-7e2d-9653-e63308b91a22` | image / image | 2 | 1 |
| 3 | `01a08a48-4878-7256-bacf-cc28dc4e1be4` | image / image | 2 | 1 |
| 3 | `01a08a48-4882-785b-8973-11cba874f698` | image / image | 2 | 1 |
| 3 | `01a08a48-488c-73d0-9ab3-480e1fcfa869` | image / image | 2 | 1 |
| 3 | `01a08a48-4896-7327-9209-0eabc9358853` | image / image | 2737 | 431 |
| 3 | `01a08a48-48b2-7e7d-85ca-379d9de3f630` | text / footer | 45 | 5 |
| 3 | `01a08a48-48bc-712a-8579-074b7cb76504` | text / page_number | 1 | 1 |
| 3 | `01a08a48-48c6-7ffd-a3d9-cd3e595c5cf5` | text / footer | 39 | 8 |
| 4 | `01a08a48-492e-7a32-9bca-3a9df3143116` | text / header | 15 | 3 |
| 4 | `01a08a48-4938-7366-a4e7-92e7e4236381` | text / header | 42 | 4 |
| 4 | `01a08a48-48d0-7431-93a1-a6b850130e66` | image / image | 4 | 2 |
| 4 | `01a08a48-48d9-7f50-87e4-57773d32d7f2` | image / image | 0 | 0 |
| 4 | `01a08a48-48e3-755c-a245-0441efa6ba0d` | image / image | 2 | 1 |
| 4 | `01a08a48-48ec-7856-abd1-e7813064b670` | image / image | 0 | 0 |
| 4 | `01a08a48-48f5-7ce9-8cb9-e74bb2505055` | image / image | 66 | 18 |
| 4 | `01a08a48-48ff-73fc-9217-2674a5e80416` | image / image | 4 | 2 |
| 4 | `01a08a48-4908-7b1e-9c70-4384aab11d05` | image / image | 0 | 0 |
| 4 | `01a08a48-4912-7344-a1d0-8990336b708f` | image / image | 1641 | 245 |
| 4 | `01a08a48-491b-77f3-8380-0a3b0b3043df` | text / text | 309 | 42 |
| 4 | `01a08a48-4925-7299-9f3e-978e427b41b9` | text / text | 320 | 48 |
| 4 | `01a08a48-4941-7fe2-90bd-2656823c57d0` | text / footer | 45 | 5 |
| 4 | `01a08a48-494b-79fa-abd9-5f140e746d88` | text / page_number | 1 | 1 |
| 4 | `01a08a48-4955-70d3-8f28-4c5c018f7a34` | text / footer | 39 | 8 |
| 5 | `01a08a48-49ab-7082-969a-30e678b8d6cd` | text / header | 15 | 3 |
| 5 | `01a08a48-49b5-7746-8356-fd8d6faaf166` | text / header | 42 | 4 |
| 5 | `01a08a48-495e-745e-9aad-8c4cd38c56fe` | text / text | 904 | 117 |
| 5 | `01a08a48-4968-7305-a539-01190e9a9b7f` | text / title | 87 | 8 |
| 5 | `01a08a48-4971-7a9a-bb92-f6ac6ff7edfe` | text / text | 2148 | 315 |
| 5 | `01a08a48-497b-73c9-8244-ada01f88c337` | text / text | 278 | 32 |
| 5 | `01a08a48-4984-7f07-9d95-af44390c8c50` | text / title | 81 | 8 |
| 5 | `01a08a48-498e-75ca-885f-a39d3da7354d` | text / text | 2026 | 278 |
| 5 | `01a08a48-4997-7984-9472-01aa130cb435` | text / title | 101 | 11 |
| 5 | `01a08a48-49a1-732a-9491-355ff1ba81da` | text / text | 525 | 69 |
| 5 | `01a08a48-49be-79be-9ffd-1f4824ce6fd0` | text / footer | 45 | 5 |
| 5 | `01a08a48-49c8-7458-a905-49526a292182` | text / page_number | 1 | 1 |
| 5 | `01a08a48-49d1-7b9b-a819-37d83f312e8c` | text / footer | 39 | 8 |
| 6 | `01a08a48-4a0c-7c0d-b983-ab10c4bd0d92` | text / header | 15 | 3 |
| 6 | `01a08a48-4a16-7164-96e4-57ff752000d9` | text / header | 42 | 4 |
| 6 | `01a08a48-49db-7859-b4fc-9234e3aee5ea` | image / image | 2 | 1 |
| 6 | `01a08a48-49e5-70c5-9ace-f4f957e1b5a9` | image / image | 2 | 1 |
| 6 | `01a08a48-49ee-7579-94cd-e4d16d13dd2a` | image / image | 2 | 1 |
| 6 | `01a08a48-49f7-7fbe-9120-60c07f14a347` | image / image | 2 | 1 |
| 6 | `01a08a48-4a02-7cf0-a629-ad021f9a295b` | image / image | 2065 | 317 |
| 6 | `01a08a48-4a20-7537-afdf-35f8ba7562a0` | text / footer | 45 | 5 |
| 6 | `01a08a48-4a2a-7f99-8b0c-81bd5bc5d685` | text / page_number | 1 | 1 |
| 6 | `01a08a48-4a35-710f-ae3b-bfdb27966cb9` | text / footer | 39 | 8 |
| 7 | `01a08a48-4a48-7211-91a4-87fb78a8652f` | text / header | 15 | 3 |
| 7 | `01a08a48-4a52-7395-8214-4def3a9066ae` | text / header | 42 | 4 |
| 7 | `01a08a48-4a3e-795c-962e-e94535c1fb7e` | image / image | 2642 | 408 |
| 7 | `01a08a48-4a5c-719e-9786-b2d96a66f354` | text / footer | 45 | 5 |
| 7 | `01a08a48-4a65-7803-b1cd-8bc663a4eb1b` | text / page_number | 1 | 1 |
| 7 | `01a08a48-4a6f-758f-a2c4-2a369268a9c7` | text / footer | 39 | 8 |
| 8 | `01a08a48-4aba-7b61-8cd3-d12e97d97a71` | text / header | 15 | 3 |
| 8 | `01a08a48-4ac3-7e9b-b743-8cebb4a4b154` | text / header | 42 | 4 |
| 8 | `01a08a48-4a78-78f1-a843-0b73d3b18401` | text / text | 2697 | 363 |
| 8 | `01a08a48-4a82-71b4-8e78-6dffabd7fae7` | text / title | 107 | 10 |
| 8 | `01a08a48-4a8b-7a37-8233-ef8e0aaab544` | text / text | 267 | 39 |
| 8 | `01a08a48-4a94-7dd1-b6ed-b97153057588` | text / text | 2049 | 276 |
| 8 | `01a08a48-4a9e-7992-9269-4b811d90e8de` | text / title | 10 | 1 |
| 8 | `01a08a48-4aa7-7b7e-a01d-f1eace0ad1cd` | text / text | 659 | 90 |
| 8 | `01a08a48-4ab1-7001-a745-524ca62dd256` | text / text | 624 | 89 |
| 8 | `01a08a48-4acd-71bc-8c90-220ccffc74e3` | text / footer | 45 | 5 |
| 8 | `01a08a48-4ad6-7428-8312-3353fabe3985` | text / page_number | 1 | 1 |
| 8 | `01a08a48-4ae0-70e2-b95b-7b93cf5cf67d` | text / footer | 39 | 8 |
| 9 | `01a08a48-4af2-7808-bbb5-e48933c63d68` | text / header | 15 | 3 |
| 9 | `01a08a48-4afc-78a5-a19c-a35fea5952d8` | text / header | 42 | 4 |
| 9 | `01a08a48-4ae9-75fe-9a2b-8ebd5395815a` | image / image | 819 | 125 |
| 9 | `01a08a48-4b06-7e6a-bdcc-c09d9e55ce5a` | text / footer | 45 | 5 |
| 9 | `01a08a48-4b11-7db2-b63f-0d8db7986508` | text / page_number | 1 | 1 |
| 9 | `01a08a48-4b1b-73aa-9243-55d2ce88d150` | text / footer | 39 | 8 |
| 10 | `01a08a48-4b85-7f38-84db-0c38ce5f33d1` | text / header | 15 | 3 |
| 10 | `01a08a48-4b8f-7409-9a3e-6a367b3a1098` | text / header | 42 | 4 |
| 10 | `01a08a48-4b25-7af0-a0ca-e9aed5bc62a6` | text / text | 1396 | 205 |
| 10 | `01a08a48-4b2f-77d2-8838-56ca0779cb67` | text / text | 563 | 78 |
| 10 | `01a08a48-4b39-70a8-b4d4-f4b56f699c6f` | text / text | 844 | 114 |
| 10 | `01a08a48-4b42-78e7-8260-3fb4a942f48a` | text / text | 749 | 106 |
| 10 | `01a08a48-4b4c-79d5-b49e-059db6e49228` | text / text | 692 | 102 |
| 10 | `01a08a48-4b56-726e-9203-4659666ea450` | text / title | 14 | 2 |
| 10 | `01a08a48-4b60-7197-a1cd-6800c8e0b155` | text / title | 4 | 1 |
| 10 | `01a08a48-4b69-7476-9c3d-ec665c12450c` | text / text | 794 | 111 |
| 10 | `01a08a48-4b72-7833-b0f3-0fae074007de` | text / title | 13 | 1 |
| 10 | `01a08a48-4b7c-780e-a762-239da8d0e58d` | text / text | 1751 | 242 |
| 10 | `01a08a48-4b99-72ea-a9c5-665719828834` | text / footer | 45 | 5 |
| 10 | `01a08a48-4ba2-7807-8670-c1955ce666bd` | text / page_number | 2 | 1 |
| 10 | `01a08a48-4bac-7374-8141-f0a96abca030` | text / footer | 39 | 8 |
| 11 | `01a08a48-4c1e-7d87-b2b7-48ec111f202b` | text / header | 15 | 3 |
| 11 | `01a08a48-4c28-7a3e-9027-cd358a6b366a` | text / header | 42 | 4 |
| 11 | `01a08a48-4bb5-798f-825a-a245aa3b917f` | image / image | 2 | 1 |
| 11 | `01a08a48-4bbf-7b72-b239-f3c0b2f99e24` | image / image | 2 | 1 |
| 11 | `01a08a48-4bc8-7ef0-9851-d4f02a1e1d68` | image / image | 2 | 1 |
| 11 | `01a08a48-4bd2-74ac-8db8-88cf4a131498` | image / image | 2 | 1 |
| 11 | `01a08a48-4bdb-7e0b-9157-e332dc8ac1ee` | image / image | 2 | 1 |
| 11 | `01a08a48-4be5-7213-8dce-7e92b18e6b31` | image / image | 2 | 1 |
| 11 | `01a08a48-4bef-71ea-b842-af731f24e2a4` | image / image | 2 | 1 |
| 11 | `01a08a48-4bf8-7e45-8acf-5aa320b9690c` | image / image | 2 | 1 |
| 11 | `01a08a48-4c02-771d-99e1-3527ca4f679e` | image / image | 0 | 0 |
| 11 | `01a08a48-4c0b-7d5d-8357-97eb3c6b5657` | image / image | 0 | 0 |
| 11 | `01a08a48-4c15-79ff-8993-90da5008b854` | image / image | 652 | 91 |
| 11 | `01a08a48-4c33-7cc4-8588-a4349c70365c` | text / footer | 45 | 5 |
| 11 | `01a08a48-4c3d-7908-89c0-6a927df6f3b1` | text / page_number | 2 | 1 |
| 11 | `01a08a48-4c46-7b38-967a-1416eb2f2317` | text / footer | 39 | 8 |
| 12 | `01a08a48-4c93-7b2e-9d8d-5c0e87894acf` | text / header | 15 | 3 |
| 12 | `01a08a48-4c9c-7eda-a8e8-548586a82d45` | text / header | 42 | 4 |
| 12 | `01a08a48-4c50-733d-abb2-12a50dd63bf2` | text / text | 1815 | 275 |
| 12 | `01a08a48-4c59-7c1a-995b-ce2d948f5397` | text / text | 672 | 92 |
| 12 | `01a08a48-4c63-7c26-b63e-4550697781bd` | text / title | 28 | 4 |
| 12 | `01a08a48-4c6d-7519-818b-87d6a325f381` | text / text | 1985 | 326 |
| 12 | `01a08a48-4c76-7ccb-b808-85d02cfbbe32` | text / text | 1105 | 182 |
| 12 | `01a08a48-4c80-7433-b49e-1baea6203a67` | text / title | 35 | 5 |
| 12 | `01a08a48-4c8a-7254-a104-3f7820573ffb` | text / text | 1408 | 207 |
| 12 | `01a08a48-4ca7-7174-be21-be0d55e407ca` | text / footer | 45 | 5 |
| 12 | `01a08a48-4cb0-7617-8bd0-033391c88cd9` | text / page_number | 2 | 1 |
| 12 | `01a08a48-4cba-711e-9a22-ac176074bf57` | text / footer | 39 | 8 |
| 13 | `01a08a48-4d49-775d-a13e-d3fb9d09eea7` | text / header | 15 | 3 |
| 13 | `01a08a48-4d53-706b-8040-0d2b85c14848` | text / header | 42 | 4 |
| 13 | `01a08a48-4cc3-7560-8788-269f70034f3e` | text / text | 1569 | 250 |
| 13 | `01a08a48-4ccd-7264-a2a5-f9a402c528e7` | text / title | 23 | 3 |
| 13 | `01a08a48-4cd6-7914-ab10-721a85650e4f` | text / text | 1599 | 227 |
| 13 | `01a08a48-4ce0-7631-85e9-21863b0f1b93` | text / text | 330 | 53 |
| 13 | `01a08a48-4ce9-7b8e-b2d0-ded8e468bc4b` | text / title | 20 | 2 |
| 13 | `01a08a48-4cf3-76e2-8ee3-c137fe494952` | text / text | 222 | 32 |
| 13 | `01a08a48-4cfc-7c07-a051-aba5ac389ab5` | text / title | 20 | 2 |
| 13 | `01a08a48-4d06-7e7e-ac10-05179c6e2fd9` | text / text | 474 | 70 |
| 13 | `01a08a48-4d10-72be-88bb-00d15d845145` | text / title | 7 | 1 |
| 13 | `01a08a48-4d19-7667-9c59-fea4fd039d20` | text / text | 670 | 105 |
| 13 | `01a08a48-4d23-7312-8bae-c1b263a249d6` | text / title | 15 | 1 |
| 13 | `01a08a48-4d2c-7fa5-9535-7814e07ac1c4` | text / text | 506 | 72 |
| 13 | `01a08a48-4d36-7320-b7d1-7096916fefd5` | text / title | 22 | 2 |
| 13 | `01a08a48-4d40-70be-9e9f-b1336bf0fa27` | text / text | 157 | 12 |
| 13 | `01a08a48-4d5c-75d0-85e0-5c2e5eb42d3f` | text / footer | 45 | 5 |
| 13 | `01a08a48-4d66-7968-9479-79283498e939` | text / page_number | 2 | 1 |
| 13 | `01a08a48-4d70-7272-939a-fe81c2cc3313` | text / footer | 39 | 8 |
| 14 | `01a08a48-4db4-7817-8899-96f21d9b0e90` | text / header | 15 | 3 |
| 14 | `01a08a48-4dbd-7b7c-bc7d-33827ab7f1e3` | text / header | 42 | 4 |
| 14 | `01a08a48-4d79-76be-9259-c45266045804` | text / title | 10 | 1 |
| 14 | `01a08a48-4d83-74f7-8e78-43c5ab345124` | text / list | 3906 | 509 |
| 14 | `01a08a48-4d8d-78ac-80cd-bc8a2549c494` | text / list | 2838 | 397 |
| 14 | `01a08a48-4d97-78f1-9ee8-c6f272c036ba` | text / text | 101 | 13 |
| 14 | `01a08a48-4da0-7ba0-a06a-9dba7bca30a6` | text / text | 182 | 28 |
| 14 | `01a08a48-4daa-776b-bd43-ff0fdf09575c` | text / text | 573 | 81 |
| 14 | `01a08a48-4dc7-77b9-b409-0fff2e443f92` | text / footer | 45 | 5 |
| 14 | `01a08a48-4dd0-7fd8-8e28-703f49dbef47` | text / page_number | 2 | 1 |
| 14 | `01a08a48-4dda-7f89-8bd1-43708c60c42b` | text / footer | 39 | 8 |

[전체 원문·segment·좌표·이미지·ID 매핑](analysis.json)
