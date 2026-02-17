--
-- PostgreSQL database dump
--

\restrict yms6b821oZOpWEqrMRy5zpnIUVjkLHJzYHNFeo837kplYqECWEVj6mG30sIS8PM

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: ads; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.ads VALUES (1, 'EXT-YO-1000', '薬用ホワイトニングジェル', '薬用ホワイトニングジェルの広告 - YouTubeで配信中', 'YOUTUBE', 'PENDING', 'BEAUTY', 'https://example.com/ads/video_1.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 4366773, 15827, '2026-01-23 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/薬用ホワイトニングジェル", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789635+00', '2026-02-12 15:15:55.78964+00');
INSERT INTO public.ads VALUES (2, 'EXT-TI-1001', 'プロテインバー24', 'プロテインバー24の広告 - TikTokで配信中', 'TIKTOK', 'PENDING', 'HEALTH', 'https://example.com/ads/video_2.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'ヘルスケアジャパン', NULL, 'ヘルスケアジャパン', NULL, NULL, NULL, 292787, 31788, '2026-01-05 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/プロテインバー24", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789642+00', '2026-02-12 15:15:55.789642+00');
INSERT INTO public.ads VALUES (3, 'EXT-FA-1002', 'オーガニック美容液', 'オーガニック美容液の広告 - Facebookで配信中', 'FACEBOOK', 'PENDING', 'EC_D2C', 'https://example.com/ads/video_3.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'ナチュラルビューティー', NULL, 'ナチュラルビューティー', NULL, NULL, NULL, 103310, 37846, '2025-12-18 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オーガニック美容液", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789646+00', '2026-02-12 15:15:55.789646+00');
INSERT INTO public.ads VALUES (4, 'EXT-IN-1003', 'AIダイエットアプリ', 'AIダイエットアプリの広告 - Instagramで配信中', 'INSTAGRAM', 'PENDING', 'APP', 'https://example.com/ads/video_4.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'フィットテック', NULL, 'フィットテック', NULL, NULL, NULL, 2823794, 33629, '2025-12-17 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/AIダイエットアプリ", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789647+00', '2026-02-12 15:15:55.789648+00');
INSERT INTO public.ads VALUES (5, 'EXT-X-1004', '即日融資カードローン', '即日融資カードローンの広告 - Xで配信中', 'X_TWITTER', 'PENDING', 'FINANCE', 'https://example.com/ads/video_5.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ファイナンスワン', NULL, 'ファイナンスワン', NULL, NULL, NULL, 1645438, 47348, '2026-02-05 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/即日融資カードローン", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789649+00', '2026-02-12 15:15:55.78965+00');
INSERT INTO public.ads VALUES (6, 'EXT-LI-1005', '高級抹茶チョコレート', '高級抹茶チョコレートの広告 - LINEで配信中', 'LINE', 'PENDING', 'FOOD', 'https://example.com/ads/video_6.mp4', NULL, NULL, 15, NULL, NULL, NULL, '京都菓子工房', NULL, '京都菓子工房', NULL, NULL, NULL, 996351, 37917, '2026-01-20 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/高級抹茶チョコレート", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.78965+00', '2026-02-12 15:15:55.789651+00');
INSERT INTO public.ads VALUES (7, 'EXT-YA-1006', 'RPG冒険王国', 'RPG冒険王国の広告 - Yahooで配信中', 'YAHOO', 'PENDING', 'GAMING', 'https://example.com/ads/video_7.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 2783356, 32130, '2025-12-21 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/RPG冒険王国", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789651+00', '2026-02-12 15:15:55.789652+00');
INSERT INTO public.ads VALUES (8, 'EXT-PI-1007', 'オンライン英会話Pro', 'オンライン英会話Proの広告 - Pinterestで配信中', 'PINTEREST', 'PENDING', 'EDUCATION', 'https://example.com/ads/video_8.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'エデュテック', NULL, 'エデュテック', NULL, NULL, NULL, 2931132, 30546, '2026-01-27 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オンライン英会話Pro", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789653+00', '2026-02-12 15:15:55.789654+00');
INSERT INTO public.ads VALUES (9, 'EXT-GO-1008', 'クラウド家計簿アプリ', 'クラウド家計簿アプリの広告 - Google Adsで配信中', 'GOOGLE_ADS', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/video_9.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 4091448, 12890, '2026-01-06 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/クラウド家計簿アプリ", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789654+00', '2026-02-12 15:15:55.789655+00');
INSERT INTO public.ads VALUES (10, 'EXT-SM-1009', 'ヒアルロン酸美容クリーム', 'ヒアルロン酸美容クリームの広告 - SmartNewsで配信中', 'SMARTNEWS', 'PENDING', 'BEAUTY', 'https://example.com/ads/video_10.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 4405243, 47067, '2026-02-11 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ヒアルロン酸美容クリーム", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789655+00', '2026-02-12 15:15:55.789656+00');
INSERT INTO public.ads VALUES (11, 'EXT-GU-1010', '糖質制限サプリメント', '糖質制限サプリメントの広告 - Gunosyで配信中', 'GUNOSY', 'PENDING', 'HEALTH', 'https://example.com/ads/video_11.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'ダイエットサポート', NULL, 'ダイエットサポート', NULL, NULL, NULL, 3650109, 41976, '2026-01-22 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/糖質制限サプリメント", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789656+00', '2026-02-12 15:15:55.789657+00');
INSERT INTO public.ads VALUES (12, 'EXT-YO-1011', 'AI翻訳ツール', 'AI翻訳ツールの広告 - YouTubeで配信中', 'YOUTUBE', 'PENDING', 'EC_D2C', 'https://example.com/ads/video_12.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'ランゲージテック', NULL, 'ランゲージテック', NULL, NULL, NULL, 589219, 27933, '2026-01-22 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/AI翻訳ツール", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789657+00', '2026-02-12 15:15:55.789658+00');
INSERT INTO public.ads VALUES (13, 'EXT-TI-1012', 'オーガニックプロテイン', 'オーガニックプロテインの広告 - TikTokで配信中', 'TIKTOK', 'PENDING', 'APP', 'https://example.com/ads/video_13.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'ボディメイク', NULL, 'ボディメイク', NULL, NULL, NULL, 1356510, 27859, '2026-01-16 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オーガニックプロテイン", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789658+00', '2026-02-12 15:15:55.789659+00');
INSERT INTO public.ads VALUES (14, 'EXT-FA-1013', '転職支援サービス', '転職支援サービスの広告 - Facebookで配信中', 'FACEBOOK', 'PENDING', 'FINANCE', 'https://example.com/ads/video_14.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 4485360, 21734, '2026-01-31 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/転職支援サービス", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789659+00', '2026-02-12 15:15:55.78966+00');
INSERT INTO public.ads VALUES (15, 'EXT-IN-1014', 'ペット保険', 'ペット保険の広告 - Instagramで配信中', 'INSTAGRAM', 'PENDING', 'FOOD', 'https://example.com/ads/video_15.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'アニマルケア', NULL, 'アニマルケア', NULL, NULL, NULL, 2101543, 12425, '2026-01-15 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ペット保険", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.78966+00', '2026-02-12 15:15:55.78966+00');
INSERT INTO public.ads VALUES (16, 'EXT-X-1015', '格安SIM', '格安SIMの広告 - Xで配信中', 'X_TWITTER', 'PENDING', 'GAMING', 'https://example.com/ads/video_16.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'モバイルセーバー', NULL, 'モバイルセーバー', NULL, NULL, NULL, 4704332, 33528, '2025-12-18 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/格安SIM", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789661+00', '2026-02-12 15:15:55.789661+00');
INSERT INTO public.ads VALUES (17, 'EXT-LI-1016', 'ストリーミングアプリ', 'ストリーミングアプリの広告 - LINEで配信中', 'LINE', 'PENDING', 'EDUCATION', 'https://example.com/ads/video_17.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'エンタメプラス', NULL, 'エンタメプラス', NULL, NULL, NULL, 962848, 35098, '2026-01-17 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ストリーミングアプリ", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789662+00', '2026-02-12 15:15:55.789662+00');
INSERT INTO public.ads VALUES (18, 'EXT-YA-1017', 'ヘアカラートリートメント', 'ヘアカラートリートメントの広告 - Yahooで配信中', 'YAHOO', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/video_18.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 611744, 27366, '2026-01-03 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ヘアカラートリートメント", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789663+00', '2026-02-12 15:15:55.789663+00');
INSERT INTO public.ads VALUES (19, 'EXT-PI-1018', 'オンライン学習塾', 'オンライン学習塾の広告 - Pinterestで配信中', 'PINTEREST', 'PENDING', 'BEAUTY', 'https://example.com/ads/video_19.mp4', NULL, NULL, 90, NULL, NULL, NULL, 'スタディAI', NULL, 'スタディAI', NULL, NULL, NULL, 1960499, 13183, '2026-01-22 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オンライン学習塾", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789666+00', '2026-02-12 15:15:55.789667+00');
INSERT INTO public.ads VALUES (20, 'EXT-GO-1019', '投資信託アプリ', '投資信託アプリの広告 - Google Adsで配信中', 'GOOGLE_ADS', 'PENDING', 'HEALTH', 'https://example.com/ads/video_20.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ウェルスナビ', NULL, 'ウェルスナビ', NULL, NULL, NULL, 2032061, 31417, '2026-02-07 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/投資信託アプリ", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789668+00', '2026-02-12 15:15:55.789668+00');
INSERT INTO public.ads VALUES (21, 'EXT-SM-1020', '薬用ホワイトニングジェル', '薬用ホワイトニングジェルの広告 - SmartNewsで配信中', 'SMARTNEWS', 'PENDING', 'EC_D2C', 'https://example.com/ads/video_21.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 2909494, 16713, '2026-01-27 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/薬用ホワイトニングジェル", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789669+00', '2026-02-12 15:15:55.789669+00');
INSERT INTO public.ads VALUES (22, 'EXT-GU-1021', 'プロテインバー24', 'プロテインバー24の広告 - Gunosyで配信中', 'GUNOSY', 'PENDING', 'APP', 'https://example.com/ads/video_22.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ヘルスケアジャパン', NULL, 'ヘルスケアジャパン', NULL, NULL, NULL, 2009403, 20177, '2026-01-17 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/プロテインバー24", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.78967+00', '2026-02-12 15:15:55.78967+00');
INSERT INTO public.ads VALUES (23, 'EXT-YO-1022', 'オーガニック美容液', 'オーガニック美容液の広告 - YouTubeで配信中', 'YOUTUBE', 'PENDING', 'FINANCE', 'https://example.com/ads/video_23.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ナチュラルビューティー', NULL, 'ナチュラルビューティー', NULL, NULL, NULL, 3418973, 45421, '2026-01-27 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オーガニック美容液", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789671+00', '2026-02-12 15:15:55.789671+00');
INSERT INTO public.ads VALUES (24, 'EXT-TI-1023', 'AIダイエットアプリ', 'AIダイエットアプリの広告 - TikTokで配信中', 'TIKTOK', 'PENDING', 'FOOD', 'https://example.com/ads/video_24.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'フィットテック', NULL, 'フィットテック', NULL, NULL, NULL, 398433, 7033, '2026-01-09 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/AIダイエットアプリ", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789672+00', '2026-02-12 15:15:55.789672+00');
INSERT INTO public.ads VALUES (25, 'EXT-FA-1024', '即日融資カードローン', '即日融資カードローンの広告 - Facebookで配信中', 'FACEBOOK', 'PENDING', 'GAMING', 'https://example.com/ads/video_25.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ファイナンスワン', NULL, 'ファイナンスワン', NULL, NULL, NULL, 1594062, 47892, '2025-12-15 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/即日融資カードローン", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789673+00', '2026-02-12 15:15:55.789673+00');
INSERT INTO public.ads VALUES (26, 'EXT-IN-1025', '高級抹茶チョコレート', '高級抹茶チョコレートの広告 - Instagramで配信中', 'INSTAGRAM', 'PENDING', 'EDUCATION', 'https://example.com/ads/video_26.mp4', NULL, NULL, 60, NULL, NULL, NULL, '京都菓子工房', NULL, '京都菓子工房', NULL, NULL, NULL, 1309433, 37732, '2025-12-28 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/高級抹茶チョコレート", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789673+00', '2026-02-12 15:15:55.789674+00');
INSERT INTO public.ads VALUES (27, 'EXT-X-1026', 'RPG冒険王国', 'RPG冒険王国の広告 - Xで配信中', 'X_TWITTER', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/video_27.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 1804462, 33712, '2025-12-26 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/RPG冒険王国", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789674+00', '2026-02-12 15:15:55.789675+00');
INSERT INTO public.ads VALUES (28, 'EXT-LI-1027', 'オンライン英会話Pro', 'オンライン英会話Proの広告 - LINEで配信中', 'LINE', 'PENDING', 'BEAUTY', 'https://example.com/ads/video_28.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'エデュテック', NULL, 'エデュテック', NULL, NULL, NULL, 1508954, 2990, '2026-01-30 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オンライン英会話Pro", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789675+00', '2026-02-12 15:15:55.789676+00');
INSERT INTO public.ads VALUES (29, 'EXT-YA-1028', 'クラウド家計簿アプリ', 'クラウド家計簿アプリの広告 - Yahooで配信中', 'YAHOO', 'PENDING', 'HEALTH', 'https://example.com/ads/video_29.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 1208285, 8671, '2026-01-21 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/クラウド家計簿アプリ", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789676+00', '2026-02-12 15:15:55.789677+00');
INSERT INTO public.ads VALUES (30, 'EXT-PI-1029', 'ヒアルロン酸美容クリーム', 'ヒアルロン酸美容クリームの広告 - Pinterestで配信中', 'PINTEREST', 'PENDING', 'EC_D2C', 'https://example.com/ads/video_30.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 2356460, 11326, '2026-02-09 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ヒアルロン酸美容クリーム", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.78968+00', '2026-02-12 15:15:55.78968+00');
INSERT INTO public.ads VALUES (31, 'EXT-GO-1030', '糖質制限サプリメント', '糖質制限サプリメントの広告 - Google Adsで配信中', 'GOOGLE_ADS', 'PENDING', 'APP', 'https://example.com/ads/video_31.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'ダイエットサポート', NULL, 'ダイエットサポート', NULL, NULL, NULL, 4494989, 39072, '2025-12-30 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/糖質制限サプリメント", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789681+00', '2026-02-12 15:15:55.789681+00');
INSERT INTO public.ads VALUES (32, 'EXT-SM-1031', 'AI翻訳ツール', 'AI翻訳ツールの広告 - SmartNewsで配信中', 'SMARTNEWS', 'PENDING', 'FINANCE', 'https://example.com/ads/video_32.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ランゲージテック', NULL, 'ランゲージテック', NULL, NULL, NULL, 1131973, 9691, '2025-12-27 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/AI翻訳ツール", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789682+00', '2026-02-12 15:15:55.789682+00');
INSERT INTO public.ads VALUES (33, 'EXT-GU-1032', 'オーガニックプロテイン', 'オーガニックプロテインの広告 - Gunosyで配信中', 'GUNOSY', 'PENDING', 'FOOD', 'https://example.com/ads/video_33.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ボディメイク', NULL, 'ボディメイク', NULL, NULL, NULL, 3084014, 2702, '2026-01-09 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オーガニックプロテイン", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789683+00', '2026-02-12 15:15:55.789683+00');
INSERT INTO public.ads VALUES (34, 'EXT-YO-1033', '転職支援サービス', '転職支援サービスの広告 - YouTubeで配信中', 'YOUTUBE', 'PENDING', 'GAMING', 'https://example.com/ads/video_34.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 1851352, 39261, '2025-12-24 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/転職支援サービス", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789684+00', '2026-02-12 15:15:55.789684+00');
INSERT INTO public.ads VALUES (35, 'EXT-TI-1034', 'ペット保険', 'ペット保険の広告 - TikTokで配信中', 'TIKTOK', 'PENDING', 'EDUCATION', 'https://example.com/ads/video_35.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'アニマルケア', NULL, 'アニマルケア', NULL, NULL, NULL, 1418401, 16209, '2026-01-04 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ペット保険", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789685+00', '2026-02-12 15:15:55.789685+00');
INSERT INTO public.ads VALUES (36, 'EXT-FA-1035', '格安SIM', '格安SIMの広告 - Facebookで配信中', 'FACEBOOK', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/video_36.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'モバイルセーバー', NULL, 'モバイルセーバー', NULL, NULL, NULL, 2771112, 4568, '2025-12-14 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/格安SIM", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789686+00', '2026-02-12 15:15:55.789686+00');
INSERT INTO public.ads VALUES (37, 'EXT-IN-1036', 'ストリーミングアプリ', 'ストリーミングアプリの広告 - Instagramで配信中', 'INSTAGRAM', 'PENDING', 'BEAUTY', 'https://example.com/ads/video_37.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'エンタメプラス', NULL, 'エンタメプラス', NULL, NULL, NULL, 596193, 41714, '2025-12-26 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ストリーミングアプリ", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789687+00', '2026-02-12 15:15:55.789687+00');
INSERT INTO public.ads VALUES (38, 'EXT-X-1037', 'ヘアカラートリートメント', 'ヘアカラートリートメントの広告 - Xで配信中', 'X_TWITTER', 'PENDING', 'HEALTH', 'https://example.com/ads/video_38.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 113655, 27846, '2025-12-28 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ヘアカラートリートメント", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789687+00', '2026-02-12 15:15:55.789688+00');
INSERT INTO public.ads VALUES (39, 'EXT-LI-1038', 'オンライン学習塾', 'オンライン学習塾の広告 - LINEで配信中', 'LINE', 'PENDING', 'EC_D2C', 'https://example.com/ads/video_39.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'スタディAI', NULL, 'スタディAI', NULL, NULL, NULL, 3743169, 44810, '2026-01-02 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オンライン学習塾", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789688+00', '2026-02-12 15:15:55.789689+00');
INSERT INTO public.ads VALUES (40, 'EXT-YA-1039', '投資信託アプリ', '投資信託アプリの広告 - Yahooで配信中', 'YAHOO', 'PENDING', 'APP', 'https://example.com/ads/video_40.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'ウェルスナビ', NULL, 'ウェルスナビ', NULL, NULL, NULL, 3444694, 3995, '2026-01-23 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/投資信託アプリ", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789689+00', '2026-02-12 15:15:55.78969+00');
INSERT INTO public.ads VALUES (41, 'EXT-PI-1040', '薬用ホワイトニングジェル', '薬用ホワイトニングジェルの広告 - Pinterestで配信中', 'PINTEREST', 'PENDING', 'FINANCE', 'https://example.com/ads/video_41.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 3884329, 19593, '2026-01-22 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/薬用ホワイトニングジェル", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.78969+00', '2026-02-12 15:15:55.789691+00');
INSERT INTO public.ads VALUES (42, 'EXT-GO-1041', 'プロテインバー24', 'プロテインバー24の広告 - Google Adsで配信中', 'GOOGLE_ADS', 'PENDING', 'FOOD', 'https://example.com/ads/video_42.mp4', NULL, NULL, 90, NULL, NULL, NULL, 'ヘルスケアジャパン', NULL, 'ヘルスケアジャパン', NULL, NULL, NULL, 3684967, 17393, '2026-01-31 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/プロテインバー24", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789691+00', '2026-02-12 15:15:55.789692+00');
INSERT INTO public.ads VALUES (43, 'EXT-SM-1042', 'オーガニック美容液', 'オーガニック美容液の広告 - SmartNewsで配信中', 'SMARTNEWS', 'PENDING', 'GAMING', 'https://example.com/ads/video_43.mp4', NULL, NULL, 90, NULL, NULL, NULL, 'ナチュラルビューティー', NULL, 'ナチュラルビューティー', NULL, NULL, NULL, 3868748, 42812, '2026-01-07 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オーガニック美容液", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789692+00', '2026-02-12 15:15:55.789693+00');
INSERT INTO public.ads VALUES (44, 'EXT-GU-1043', 'AIダイエットアプリ', 'AIダイエットアプリの広告 - Gunosyで配信中', 'GUNOSY', 'PENDING', 'EDUCATION', 'https://example.com/ads/video_44.mp4', NULL, NULL, 90, NULL, NULL, NULL, 'フィットテック', NULL, 'フィットテック', NULL, NULL, NULL, 964460, 48529, '2026-01-19 15:15:55.710739+00', '2026-02-12 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/AIダイエットアプリ", "destination_type": "EC"}', '[]', '2026-02-12 15:15:55.789693+00', '2026-02-12 15:15:55.789694+00');
INSERT INTO public.ads VALUES (45, 'EXT-YO-1044', '即日融資カードローン', '即日融資カードローンの広告 - YouTubeで配信中', 'YOUTUBE', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/video_45.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'ファイナンスワン', NULL, 'ファイナンスワン', NULL, NULL, NULL, 2781870, 22547, '2026-02-08 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/即日融資カードローン", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789694+00', '2026-02-12 15:15:55.789694+00');
INSERT INTO public.ads VALUES (46, 'EXT-TI-1045', '高級抹茶チョコレート', '高級抹茶チョコレートの広告 - TikTokで配信中', 'TIKTOK', 'PENDING', 'BEAUTY', 'https://example.com/ads/video_46.mp4', NULL, NULL, 30, NULL, NULL, NULL, '京都菓子工房', NULL, '京都菓子工房', NULL, NULL, NULL, 743692, 40820, '2026-01-18 15:15:55.710739+00', '2026-02-09 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/高級抹茶チョコレート", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789695+00', '2026-02-12 15:15:55.789695+00');
INSERT INTO public.ads VALUES (47, 'EXT-FA-1046', 'RPG冒険王国', 'RPG冒険王国の広告 - Facebookで配信中', 'FACEBOOK', 'PENDING', 'HEALTH', 'https://example.com/ads/video_47.mp4', NULL, NULL, 120, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 888663, 44558, '2026-01-30 15:15:55.710739+00', '2026-02-10 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/RPG冒険王国", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789696+00', '2026-02-12 15:15:55.789696+00');
INSERT INTO public.ads VALUES (48, 'EXT-IN-1047', 'オンライン英会話Pro', 'オンライン英会話Proの広告 - Instagramで配信中', 'INSTAGRAM', 'PENDING', 'EC_D2C', 'https://example.com/ads/video_48.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'エデュテック', NULL, 'エデュテック', NULL, NULL, NULL, 3387985, 14656, '2025-12-20 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/オンライン英会話Pro", "destination_type": "アプリストア"}', '[]', '2026-02-12 15:15:55.789697+00', '2026-02-12 15:15:55.789697+00');
INSERT INTO public.ads VALUES (49, 'EXT-X-1048', 'クラウド家計簿アプリ', 'クラウド家計簿アプリの広告 - Xで配信中', 'X_TWITTER', 'PENDING', 'APP', 'https://example.com/ads/video_49.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 1363479, 48661, '2025-12-26 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/クラウド家計簿アプリ", "destination_type": "直LP"}', '[]', '2026-02-12 15:15:55.789698+00', '2026-02-12 15:15:55.789698+00');
INSERT INTO public.ads VALUES (50, 'EXT-LI-1049', 'ヒアルロン酸美容クリーム', 'ヒアルロン酸美容クリームの広告 - LINEで配信中', 'LINE', 'PENDING', 'FINANCE', 'https://example.com/ads/video_50.mp4', NULL, NULL, 90, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 4485499, 31692, '2026-02-07 15:15:55.710739+00', '2026-02-11 15:15:55.710739+00', '{"destination_url": "https://example.com/lp/ヒアルロン酸美容クリーム", "destination_type": "記事LP"}', '[]', '2026-02-12 15:15:55.789699+00', '2026-02-12 15:15:55.789699+00');
INSERT INTO public.ads VALUES (51, 'EXT-YO-51', '美容サプリ - ボディメイク広告1', '美容サプリに関するyoutube広告', 'YOUTUBE', 'PENDING', 'EC_D2C', 'https://example.com/ads/youtube_52.mp4', NULL, '', 60, NULL, NULL, NULL, 'ボディメイク', NULL, 'ボディメイク', NULL, NULL, NULL, 1474927, 17467, '2026-01-20 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "EC"}', '["美容サプリ", "youtube", "ec_d2c"]', '2026-02-12 16:15:45.979266+00', '2026-02-12 16:15:45.979271+00');
INSERT INTO public.ads VALUES (52, 'EXT-YO-52', '美容サプリ - スタディAI広告2', '美容サプリに関するyoutube広告', 'YOUTUBE', 'PENDING', 'GAMING', 'https://example.com/ads/youtube_53.mp4', NULL, '', 60, NULL, NULL, NULL, 'スタディAI', NULL, 'スタディAI', NULL, NULL, NULL, 1650049, 16196, '2026-01-20 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "EC"}', '["美容サプリ", "youtube", "gaming"]', '2026-02-12 16:15:45.979272+00', '2026-02-12 16:15:45.979273+00');
INSERT INTO public.ads VALUES (53, 'EXT-YO-53', '美容サプリ - エデュテック広告3', '美容サプリに関するyoutube広告', 'YOUTUBE', 'PENDING', 'APP', 'https://example.com/ads/youtube_54.mp4', NULL, '', 90, NULL, NULL, NULL, 'エデュテック', NULL, 'エデュテック', NULL, NULL, NULL, 3258599, 62588, '2026-02-01 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "アプリストア"}', '["美容サプリ", "youtube", "app"]', '2026-02-12 16:15:45.979273+00', '2026-02-12 16:15:45.979276+00');
INSERT INTO public.ads VALUES (54, 'EXT-YO-54', '美容サプリ - カラーラボ広告4', '美容サプリに関するyoutube広告', 'YOUTUBE', 'PENDING', 'APP', 'https://example.com/ads/youtube_55.mp4', NULL, '', 30, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 2744838, 9377, '2026-01-31 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "直LP"}', '["美容サプリ", "youtube", "app"]', '2026-02-12 16:15:45.979277+00', '2026-02-12 16:15:45.979278+00');
INSERT INTO public.ads VALUES (55, 'EXT-YO-55', '美容サプリ - キャリアナビ広告5', '美容サプリに関するyoutube広告', 'YOUTUBE', 'PENDING', 'EC_D2C', 'https://example.com/ads/youtube_56.mp4', NULL, '', 15, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 2684560, 44160, '2026-01-23 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "アプリストア"}', '["美容サプリ", "youtube", "ec_d2c"]', '2026-02-12 16:15:45.979278+00', '2026-02-12 16:15:45.979279+00');
INSERT INTO public.ads VALUES (56, 'EXT-TI-56', '美容サプリ - ボディメイク広告1', '美容サプリに関するtiktok広告', 'TIKTOK', 'PENDING', 'HEALTH', 'https://example.com/ads/tiktok_57.mp4', NULL, '', 15, NULL, NULL, NULL, 'ボディメイク', NULL, 'ボディメイク', NULL, NULL, NULL, 605129, 3057, '2026-01-21 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "記事LP"}', '["美容サプリ", "tiktok", "health"]', '2026-02-12 16:15:45.979279+00', '2026-02-12 16:15:45.97928+00');
INSERT INTO public.ads VALUES (57, 'EXT-TI-57', '美容サプリ - モバイルセーバー広告2', '美容サプリに関するtiktok広告', 'TIKTOK', 'PENDING', 'FOOD', 'https://example.com/ads/tiktok_58.mp4', NULL, '', 90, NULL, NULL, NULL, 'モバイルセーバー', NULL, 'モバイルセーバー', NULL, NULL, NULL, 4625968, 83036, '2026-02-12 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "アプリストア"}', '["美容サプリ", "tiktok", "food"]', '2026-02-12 16:15:45.97928+00', '2026-02-12 16:15:45.97928+00');
INSERT INTO public.ads VALUES (58, 'EXT-TI-58', '美容サプリ - フィットテック広告3', '美容サプリに関するtiktok広告', 'TIKTOK', 'PENDING', 'EC_D2C', 'https://example.com/ads/tiktok_59.mp4', NULL, '', 90, NULL, NULL, NULL, 'フィットテック', NULL, 'フィットテック', NULL, NULL, NULL, 4629519, 25292, '2026-01-26 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "EC"}', '["美容サプリ", "tiktok", "ec_d2c"]', '2026-02-12 16:15:45.979281+00', '2026-02-12 16:15:45.979282+00');
INSERT INTO public.ads VALUES (59, 'EXT-TI-59', '美容サプリ - エンタメプラス広告4', '美容サプリに関するtiktok広告', 'TIKTOK', 'PENDING', 'APP', 'https://example.com/ads/tiktok_60.mp4', NULL, '', 90, NULL, NULL, NULL, 'エンタメプラス', NULL, 'エンタメプラス', NULL, NULL, NULL, 1176442, 3242, '2026-01-29 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "記事LP"}', '["美容サプリ", "tiktok", "app"]', '2026-02-12 16:15:45.979282+00', '2026-02-12 16:15:45.979283+00');
INSERT INTO public.ads VALUES (60, 'EXT-TI-60', '美容サプリ - キャリアナビ広告5', '美容サプリに関するtiktok広告', 'TIKTOK', 'PENDING', 'BEAUTY', 'https://example.com/ads/tiktok_61.mp4', NULL, '', 60, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 552312, 4736, '2026-02-05 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "アプリストア"}', '["美容サプリ", "tiktok", "beauty"]', '2026-02-12 16:15:45.979283+00', '2026-02-12 16:15:45.979284+00');
INSERT INTO public.ads VALUES (61, 'EXT-IN-61', '美容サプリ - エンタメプラス広告1', '美容サプリに関するinstagram広告', 'INSTAGRAM', 'PENDING', 'FOOD', 'https://example.com/ads/instagram_62.mp4', NULL, '', 60, NULL, NULL, NULL, 'エンタメプラス', NULL, 'エンタメプラス', NULL, NULL, NULL, 1120548, 18929, '2026-01-20 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "アプリストア"}', '["美容サプリ", "instagram", "food"]', '2026-02-12 16:15:45.979284+00', '2026-02-12 16:15:45.979285+00');
INSERT INTO public.ads VALUES (62, 'EXT-IN-62', '美容サプリ - アニマルケア広告2', '美容サプリに関するinstagram広告', 'INSTAGRAM', 'PENDING', 'EC_D2C', 'https://example.com/ads/instagram_63.mp4', NULL, '', 15, NULL, NULL, NULL, 'アニマルケア', NULL, 'アニマルケア', NULL, NULL, NULL, 3157773, 3774, '2026-01-22 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "EC"}', '["美容サプリ", "instagram", "ec_d2c"]', '2026-02-12 16:15:45.979285+00', '2026-02-12 16:15:45.979285+00');
INSERT INTO public.ads VALUES (63, 'EXT-IN-63', '美容サプリ - エデュテック広告3', '美容サプリに関するinstagram広告', 'INSTAGRAM', 'PENDING', 'HEALTH', 'https://example.com/ads/instagram_64.mp4', NULL, '', 60, NULL, NULL, NULL, 'エデュテック', NULL, 'エデュテック', NULL, NULL, NULL, 2254712, 11090, '2026-01-30 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "直LP"}', '["美容サプリ", "instagram", "health"]', '2026-02-12 16:15:45.979286+00', '2026-02-12 16:15:45.979286+00');
INSERT INTO public.ads VALUES (64, 'EXT-IN-64', '美容サプリ - ゲームスタジオX広告4', '美容サプリに関するinstagram広告', 'INSTAGRAM', 'PENDING', 'HEALTH', 'https://example.com/ads/instagram_65.mp4', NULL, '', 90, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 2329507, 45911, '2026-01-21 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "直LP"}', '["美容サプリ", "instagram", "health"]', '2026-02-12 16:15:45.979287+00', '2026-02-12 16:15:45.979287+00');
INSERT INTO public.ads VALUES (65, 'EXT-IN-65', '美容サプリ - フィットテック広告5', '美容サプリに関するinstagram広告', 'INSTAGRAM', 'PENDING', 'EC_D2C', 'https://example.com/ads/instagram_66.mp4', NULL, '', 90, NULL, NULL, NULL, 'フィットテック', NULL, 'フィットテック', NULL, NULL, NULL, 2268850, 18770, '2026-02-09 16:15:45.868016+00', '2026-02-12 16:15:45.868016+00', '{"crawl_query": "美容サプリ", "destination_url": "https://example.com/lp/美容サプリ", "destination_type": "EC"}', '["美容サプリ", "instagram", "ec_d2c"]', '2026-02-12 16:15:45.979287+00', '2026-02-12 16:15:45.979288+00');
INSERT INTO public.ads VALUES (66, 'EXT-YO-66', 'ダイエット食品 - アニマルケア広告1', 'ダイエット食品に関するyoutube広告', 'YOUTUBE', 'PENDING', 'EDUCATION', 'https://example.com/ads/youtube_67.mp4', NULL, '', 30, NULL, NULL, NULL, 'アニマルケア', NULL, 'アニマルケア', NULL, NULL, NULL, 1599213, 15378, '2026-01-23 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "youtube", "education"]', '2026-02-12 16:15:57.578589+00', '2026-02-12 16:15:57.578594+00');
INSERT INTO public.ads VALUES (67, 'EXT-YO-67', 'ダイエット食品 - フィットテック広告2', 'ダイエット食品に関するyoutube広告', 'YOUTUBE', 'PENDING', 'APP', 'https://example.com/ads/youtube_68.mp4', NULL, '', 120, NULL, NULL, NULL, 'フィットテック', NULL, 'フィットテック', NULL, NULL, NULL, 3176667, 42491, '2026-02-06 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "youtube", "app"]', '2026-02-12 16:15:57.578595+00', '2026-02-12 16:15:57.578595+00');
INSERT INTO public.ads VALUES (68, 'EXT-YO-68', 'ダイエット食品 - カラーラボ広告3', 'ダイエット食品に関するyoutube広告', 'YOUTUBE', 'PENDING', 'EDUCATION', 'https://example.com/ads/youtube_69.mp4', NULL, '', 30, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 3547450, 55956, '2026-01-27 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "アプリストア"}', '["ダイエット食品", "youtube", "education"]', '2026-02-12 16:15:57.578596+00', '2026-02-12 16:15:57.578597+00');
INSERT INTO public.ads VALUES (69, 'EXT-TI-69', 'ダイエット食品 - 京都菓子工房広告1', 'ダイエット食品に関するtiktok広告', 'TIKTOK', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/tiktok_70.mp4', NULL, '', 60, NULL, NULL, NULL, '京都菓子工房', NULL, '京都菓子工房', NULL, NULL, NULL, 2554792, 22602, '2026-02-01 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "tiktok", "technology"]', '2026-02-12 16:15:57.578597+00', '2026-02-12 16:15:57.578598+00');
INSERT INTO public.ads VALUES (70, 'EXT-TI-70', 'ダイエット食品 - ゲームスタジオX広告2', 'ダイエット食品に関するtiktok広告', 'TIKTOK', 'PENDING', 'HEALTH', 'https://example.com/ads/tiktok_71.mp4', NULL, '', 120, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 3502631, 20550, '2026-01-15 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "tiktok", "health"]', '2026-02-12 16:15:57.578598+00', '2026-02-12 16:15:57.578599+00');
INSERT INTO public.ads VALUES (71, 'EXT-TI-71', 'ダイエット食品 - スタディAI広告3', 'ダイエット食品に関するtiktok広告', 'TIKTOK', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/tiktok_72.mp4', NULL, '', 120, NULL, NULL, NULL, 'スタディAI', NULL, 'スタディAI', NULL, NULL, NULL, 4416114, 30933, '2026-01-29 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "tiktok", "technology"]', '2026-02-12 16:15:57.578599+00', '2026-02-12 16:15:57.5786+00');
INSERT INTO public.ads VALUES (72, 'EXT-IN-72', 'ダイエット食品 - ビューティーラボ広告1', 'ダイエット食品に関するinstagram広告', 'INSTAGRAM', 'PENDING', 'GAMING', 'https://example.com/ads/instagram_73.mp4', NULL, '', 60, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 498686, 3301, '2026-02-09 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "instagram", "gaming"]', '2026-02-12 16:15:57.5786+00', '2026-02-12 16:15:57.5786+00');
INSERT INTO public.ads VALUES (73, 'EXT-IN-73', 'ダイエット食品 - カラーラボ広告2', 'ダイエット食品に関するinstagram広告', 'INSTAGRAM', 'PENDING', 'BEAUTY', 'https://example.com/ads/instagram_74.mp4', NULL, '', 90, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 1972555, 37090, '2026-02-03 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "instagram", "beauty"]', '2026-02-12 16:15:57.578601+00', '2026-02-12 16:15:57.578602+00');
INSERT INTO public.ads VALUES (74, 'EXT-IN-74', 'ダイエット食品 - キャリアナビ広告3', 'ダイエット食品に関するinstagram広告', 'INSTAGRAM', 'PENDING', 'EDUCATION', 'https://example.com/ads/instagram_75.mp4', NULL, '', 15, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 2373425, 29045, '2026-02-04 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "instagram", "education"]', '2026-02-12 16:15:57.578602+00', '2026-02-12 16:15:57.578602+00');
INSERT INTO public.ads VALUES (75, 'EXT-FA-75', 'ダイエット食品 - マネーテック広告1', 'ダイエット食品に関するfacebook広告', 'FACEBOOK', 'PENDING', 'FINANCE', 'https://example.com/ads/facebook_76.mp4', NULL, '', 120, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 3531903, 53074, '2026-01-27 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "アプリストア"}', '["ダイエット食品", "facebook", "finance"]', '2026-02-12 16:15:57.578603+00', '2026-02-12 16:15:57.578604+00');
INSERT INTO public.ads VALUES (76, 'EXT-FA-76', 'ダイエット食品 - モバイルセーバー広告2', 'ダイエット食品に関するfacebook広告', 'FACEBOOK', 'PENDING', 'BEAUTY', 'https://example.com/ads/facebook_77.mp4', NULL, '', 90, NULL, NULL, NULL, 'モバイルセーバー', NULL, 'モバイルセーバー', NULL, NULL, NULL, 1860831, 2934, '2026-02-08 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "facebook", "beauty"]', '2026-02-12 16:15:57.578604+00', '2026-02-12 16:15:57.578604+00');
INSERT INTO public.ads VALUES (77, 'EXT-FA-77', 'ダイエット食品 - ゲームスタジオX広告3', 'ダイエット食品に関するfacebook広告', 'FACEBOOK', 'PENDING', 'APP', 'https://example.com/ads/facebook_78.mp4', NULL, '', 30, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 62419, 213, '2026-01-30 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "facebook", "app"]', '2026-02-12 16:15:57.578605+00', '2026-02-12 16:15:57.578605+00');
INSERT INTO public.ads VALUES (78, 'EXT-X-78', 'ダイエット食品 - ゲームスタジオX広告1', 'ダイエット食品に関するx_twitter広告', 'X_TWITTER', 'PENDING', 'EC_D2C', 'https://example.com/ads/x_twitter_79.mp4', NULL, '', 30, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 1366088, 9517, '2026-02-11 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "x_twitter", "ec_d2c"]', '2026-02-12 16:15:57.578606+00', '2026-02-12 16:15:57.578606+00');
INSERT INTO public.ads VALUES (79, 'EXT-X-79', 'ダイエット食品 - スキンケアプラス広告2', 'ダイエット食品に関するx_twitter広告', 'X_TWITTER', 'PENDING', 'FOOD', 'https://example.com/ads/x_twitter_80.mp4', NULL, '', 90, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 4087011, 16933, '2026-01-22 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "アプリストア"}', '["ダイエット食品", "x_twitter", "food"]', '2026-02-12 16:15:57.578607+00', '2026-02-12 16:15:57.578607+00');
INSERT INTO public.ads VALUES (80, 'EXT-X-80', 'ダイエット食品 - ダイエットサポート広告3', 'ダイエット食品に関するx_twitter広告', 'X_TWITTER', 'PENDING', 'FOOD', 'https://example.com/ads/x_twitter_81.mp4', NULL, '', 60, NULL, NULL, NULL, 'ダイエットサポート', NULL, 'ダイエットサポート', NULL, NULL, NULL, 4784182, 17231, '2026-02-01 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "x_twitter", "food"]', '2026-02-12 16:15:57.578607+00', '2026-02-12 16:15:57.578608+00');
INSERT INTO public.ads VALUES (81, 'EXT-LI-81', 'ダイエット食品 - スタディAI広告1', 'ダイエット食品に関するline広告', 'LINE', 'PENDING', 'EC_D2C', 'https://example.com/ads/line_82.mp4', NULL, '', 15, NULL, NULL, NULL, 'スタディAI', NULL, 'スタディAI', NULL, NULL, NULL, 3388004, 63786, '2026-01-30 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "line", "ec_d2c"]', '2026-02-12 16:15:57.578608+00', '2026-02-12 16:15:57.578609+00');
INSERT INTO public.ads VALUES (82, 'EXT-LI-82', 'ダイエット食品 - カラーラボ広告2', 'ダイエット食品に関するline広告', 'LINE', 'PENDING', 'EC_D2C', 'https://example.com/ads/line_83.mp4', NULL, '', 15, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 4977393, 20211, '2026-01-15 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "line", "ec_d2c"]', '2026-02-12 16:15:57.578609+00', '2026-02-12 16:15:57.578609+00');
INSERT INTO public.ads VALUES (83, 'EXT-LI-83', 'ダイエット食品 - スキンケアプラス広告3', 'ダイエット食品に関するline広告', 'LINE', 'PENDING', 'EC_D2C', 'https://example.com/ads/line_84.mp4', NULL, '', 120, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 1106092, 6969, '2026-02-01 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "line", "ec_d2c"]', '2026-02-12 16:15:57.57861+00', '2026-02-12 16:15:57.57861+00');
INSERT INTO public.ads VALUES (84, 'EXT-YA-84', 'ダイエット食品 - ビューティーラボ広告1', 'ダイエット食品に関するyahoo広告', 'YAHOO', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/yahoo_85.mp4', NULL, '', 120, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 1550558, 9382, '2026-01-17 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "yahoo", "technology"]', '2026-02-12 16:15:57.578611+00', '2026-02-12 16:15:57.578611+00');
INSERT INTO public.ads VALUES (85, 'EXT-YA-85', 'ダイエット食品 - マネーテック広告2', 'ダイエット食品に関するyahoo広告', 'YAHOO', 'PENDING', 'APP', 'https://example.com/ads/yahoo_86.mp4', NULL, '', 15, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 972248, 13301, '2026-01-19 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "yahoo", "app"]', '2026-02-12 16:15:57.578611+00', '2026-02-12 16:15:57.578612+00');
INSERT INTO public.ads VALUES (86, 'EXT-YA-86', 'ダイエット食品 - スキンケアプラス広告3', 'ダイエット食品に関するyahoo広告', 'YAHOO', 'PENDING', 'EC_D2C', 'https://example.com/ads/yahoo_87.mp4', NULL, '', 120, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 1038120, 7650, '2026-01-18 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "yahoo", "ec_d2c"]', '2026-02-12 16:15:57.578612+00', '2026-02-12 16:15:57.578613+00');
INSERT INTO public.ads VALUES (87, 'EXT-PI-87', 'ダイエット食品 - ナチュラルビューティー広告1', 'ダイエット食品に関するpinterest広告', 'PINTEREST', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/pinterest_88.mp4', NULL, '', 30, NULL, NULL, NULL, 'ナチュラルビューティー', NULL, 'ナチュラルビューティー', NULL, NULL, NULL, 1991854, 29180, '2026-01-25 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "pinterest", "technology"]', '2026-02-12 16:15:57.578613+00', '2026-02-12 16:15:57.578613+00');
INSERT INTO public.ads VALUES (88, 'EXT-PI-88', 'ダイエット食品 - ダイエットサポート広告2', 'ダイエット食品に関するpinterest広告', 'PINTEREST', 'PENDING', 'EC_D2C', 'https://example.com/ads/pinterest_89.mp4', NULL, '', 30, NULL, NULL, NULL, 'ダイエットサポート', NULL, 'ダイエットサポート', NULL, NULL, NULL, 472650, 6825, '2026-01-21 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "pinterest", "ec_d2c"]', '2026-02-12 16:15:57.578614+00', '2026-02-12 16:15:57.578614+00');
INSERT INTO public.ads VALUES (89, 'EXT-PI-89', 'ダイエット食品 - ビューティーラボ広告3', 'ダイエット食品に関するpinterest広告', 'PINTEREST', 'PENDING', 'EC_D2C', 'https://example.com/ads/pinterest_90.mp4', NULL, '', 30, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 4617403, 17760, '2026-01-22 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "EC"}', '["ダイエット食品", "pinterest", "ec_d2c"]', '2026-02-12 16:15:57.578614+00', '2026-02-12 16:15:57.578615+00');
INSERT INTO public.ads VALUES (90, 'EXT-SM-90', 'ダイエット食品 - マネーテック広告1', 'ダイエット食品に関するsmartnews広告', 'SMARTNEWS', 'PENDING', 'FOOD', 'https://example.com/ads/smartnews_91.mp4', NULL, '', 30, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 3400757, 4982, '2026-02-02 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "smartnews", "food"]', '2026-02-12 16:15:57.578615+00', '2026-02-12 16:15:57.578615+00');
INSERT INTO public.ads VALUES (91, 'EXT-SM-91', 'ダイエット食品 - エンタメプラス広告2', 'ダイエット食品に関するsmartnews広告', 'SMARTNEWS', 'PENDING', 'EC_D2C', 'https://example.com/ads/smartnews_92.mp4', NULL, '', 15, NULL, NULL, NULL, 'エンタメプラス', NULL, 'エンタメプラス', NULL, NULL, NULL, 2227584, 19502, '2026-02-06 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "smartnews", "ec_d2c"]', '2026-02-12 16:15:57.578616+00', '2026-02-12 16:15:57.578616+00');
INSERT INTO public.ads VALUES (92, 'EXT-SM-92', 'ダイエット食品 - スタディAI広告3', 'ダイエット食品に関するsmartnews広告', 'SMARTNEWS', 'PENDING', 'GAMING', 'https://example.com/ads/smartnews_93.mp4', NULL, '', 60, NULL, NULL, NULL, 'スタディAI', NULL, 'スタディAI', NULL, NULL, NULL, 3025999, 411, '2026-02-06 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "smartnews", "gaming"]', '2026-02-12 16:15:57.578617+00', '2026-02-12 16:15:57.578617+00');
INSERT INTO public.ads VALUES (93, 'EXT-GO-93', 'ダイエット食品 - カラーラボ広告1', 'ダイエット食品に関するgoogle_ads広告', 'GOOGLE_ADS', 'PENDING', 'EDUCATION', 'https://example.com/ads/google_ads_94.mp4', NULL, '', 30, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 2769979, 6606, '2026-01-17 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "google_ads", "education"]', '2026-02-12 16:15:57.578617+00', '2026-02-12 16:15:57.578618+00');
INSERT INTO public.ads VALUES (94, 'EXT-GO-94', 'ダイエット食品 - マネーテック広告2', 'ダイエット食品に関するgoogle_ads広告', 'GOOGLE_ADS', 'PENDING', 'FINANCE', 'https://example.com/ads/google_ads_95.mp4', NULL, '', 30, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 3982274, 78304, '2026-02-07 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "google_ads", "finance"]', '2026-02-12 16:15:57.578618+00', '2026-02-12 16:15:57.578619+00');
INSERT INTO public.ads VALUES (95, 'EXT-GO-95', 'ダイエット食品 - ウェルスナビ広告3', 'ダイエット食品に関するgoogle_ads広告', 'GOOGLE_ADS', 'PENDING', 'EDUCATION', 'https://example.com/ads/google_ads_96.mp4', NULL, '', 90, NULL, NULL, NULL, 'ウェルスナビ', NULL, 'ウェルスナビ', NULL, NULL, NULL, 4975336, 4870, '2026-01-19 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "アプリストア"}', '["ダイエット食品", "google_ads", "education"]', '2026-02-12 16:15:57.578619+00', '2026-02-12 16:15:57.578619+00');
INSERT INTO public.ads VALUES (96, 'EXT-GU-96', 'ダイエット食品 - ランゲージテック広告1', 'ダイエット食品に関するgunosy広告', 'GUNOSY', 'PENDING', 'EC_D2C', 'https://example.com/ads/gunosy_97.mp4', NULL, '', 30, NULL, NULL, NULL, 'ランゲージテック', NULL, 'ランゲージテック', NULL, NULL, NULL, 1112620, 16512, '2026-01-26 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "gunosy", "ec_d2c"]', '2026-02-12 16:15:57.57862+00', '2026-02-12 16:15:57.57862+00');
INSERT INTO public.ads VALUES (97, 'EXT-GU-97', 'ダイエット食品 - エデュテック広告2', 'ダイエット食品に関するgunosy広告', 'GUNOSY', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/gunosy_98.mp4', NULL, '', 60, NULL, NULL, NULL, 'エデュテック', NULL, 'エデュテック', NULL, NULL, NULL, 1746196, 21493, '2026-02-09 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "記事LP"}', '["ダイエット食品", "gunosy", "technology"]', '2026-02-12 16:15:57.578621+00', '2026-02-12 16:15:57.578621+00');
INSERT INTO public.ads VALUES (98, 'EXT-GU-98', 'ダイエット食品 - ヘルスケアジャパン広告3', 'ダイエット食品に関するgunosy広告', 'GUNOSY', 'PENDING', 'EDUCATION', 'https://example.com/ads/gunosy_99.mp4', NULL, '', 60, NULL, NULL, NULL, 'ヘルスケアジャパン', NULL, 'ヘルスケアジャパン', NULL, NULL, NULL, 990430, 19588, '2026-02-04 16:15:57.572957+00', '2026-02-12 16:15:57.572957+00', '{"crawl_query": "ダイエット食品", "destination_url": "https://example.com/lp/ダイエット食品", "destination_type": "直LP"}', '["ダイエット食品", "gunosy", "education"]', '2026-02-12 16:15:57.578622+00', '2026-02-12 16:15:57.578622+00');
INSERT INTO public.ads VALUES (99, 'EXT-YO-99', 'プロテイン - ダイエットサポート広告1', 'プロテインに関するyoutube広告', 'YOUTUBE', 'PENDING', 'GAMING', 'https://example.com/ads/youtube_100.mp4', NULL, '', 15, NULL, NULL, NULL, 'ダイエットサポート', NULL, 'ダイエットサポート', NULL, NULL, NULL, 1221360, 1722, '2026-01-21 23:37:22.93699+00', '2026-02-12 23:37:22.93699+00', '{"crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "記事LP"}', '["プロテイン", "youtube", "gaming"]', '2026-02-12 23:37:22.944136+00', '2026-02-12 23:37:22.94414+00');
INSERT INTO public.ads VALUES (100, 'EXT-YO-100', 'プロテイン - キャリアナビ広告2', 'プロテインに関するyoutube広告', 'YOUTUBE', 'PENDING', 'HEALTH', 'https://example.com/ads/youtube_101.mp4', NULL, '', 15, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 4326337, 19432, '2026-01-31 23:37:22.93699+00', '2026-02-12 23:37:22.93699+00', '{"crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "アプリストア"}', '["プロテイン", "youtube", "health"]', '2026-02-12 23:37:22.944141+00', '2026-02-12 23:37:22.944142+00');
INSERT INTO public.ads VALUES (101, 'EXT-YO-101', 'プロテイン - ダイエットサポート広告3', 'プロテインに関するyoutube広告', 'YOUTUBE', 'PENDING', 'EDUCATION', 'https://example.com/ads/youtube_102.mp4', NULL, '', 120, NULL, NULL, NULL, 'ダイエットサポート', NULL, 'ダイエットサポート', NULL, NULL, NULL, 2578437, 45657, '2026-02-08 23:37:22.93699+00', '2026-02-12 23:37:22.93699+00', '{"crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "アプリストア"}', '["プロテイン", "youtube", "education"]', '2026-02-12 23:37:22.944143+00', '2026-02-12 23:37:22.944145+00');
INSERT INTO public.ads VALUES (102, 'EXT-TI-102', 'プロテイン - ウェルスナビ広告1', 'プロテインに関するtiktok広告', 'TIKTOK', 'PENDING', 'EC_D2C', 'https://example.com/ads/tiktok_103.mp4', NULL, '', 30, NULL, NULL, NULL, 'ウェルスナビ', NULL, 'ウェルスナビ', NULL, NULL, NULL, 4255199, 76275, '2026-01-30 23:37:22.93699+00', '2026-02-12 23:37:22.93699+00', '{"crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "直LP"}', '["プロテイン", "tiktok", "ec_d2c"]', '2026-02-12 23:37:22.944146+00', '2026-02-12 23:37:22.944147+00');
INSERT INTO public.ads VALUES (103, 'EXT-TI-103', 'プロテイン - スキンケアプラス広告2', 'プロテインに関するtiktok広告', 'TIKTOK', 'PENDING', 'EDUCATION', 'https://example.com/ads/tiktok_104.mp4', NULL, '', 90, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 2286955, 23081, '2026-02-11 23:37:22.93699+00', '2026-02-12 23:37:22.93699+00', '{"crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "アプリストア"}', '["プロテイン", "tiktok", "education"]', '2026-02-12 23:37:22.944148+00', '2026-02-12 23:37:22.944149+00');
INSERT INTO public.ads VALUES (104, 'EXT-TI-104', 'プロテイン - エンタメプラス広告3', 'プロテインに関するtiktok広告', 'TIKTOK', 'PENDING', 'FOOD', 'https://example.com/ads/tiktok_105.mp4', NULL, '', 120, NULL, NULL, NULL, 'エンタメプラス', NULL, 'エンタメプラス', NULL, NULL, NULL, 1445287, 1704, '2026-02-07 23:37:22.93699+00', '2026-02-12 23:37:22.93699+00', '{"crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "EC"}', '["プロテイン", "tiktok", "food"]', '2026-02-12 23:37:22.944149+00', '2026-02-12 23:37:22.944149+00');
INSERT INTO public.ads VALUES (105, 'EXT-YO-105', 'スキンケア - ナチュラルビューティー広告1', 'スキンケアに関するyoutube広告', 'YOUTUBE', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/youtube_106.mp4', NULL, '', 120, NULL, NULL, NULL, 'ナチュラルビューティー', NULL, 'ナチュラルビューティー', NULL, NULL, NULL, 1626709, 24393, '2026-02-09 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "youtube", "technology"]', '2026-02-12 23:40:23.562673+00', '2026-02-12 23:40:23.562677+00');
INSERT INTO public.ads VALUES (106, 'EXT-YO-106', 'スキンケア - アニマルケア広告2', 'スキンケアに関するyoutube広告', 'YOUTUBE', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/youtube_107.mp4', NULL, '', 120, NULL, NULL, NULL, 'アニマルケア', NULL, 'アニマルケア', NULL, NULL, NULL, 590162, 5126, '2026-02-09 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "記事LP"}', '["スキンケア", "youtube", "technology"]', '2026-02-12 23:40:23.562679+00', '2026-02-12 23:40:23.562679+00');
INSERT INTO public.ads VALUES (107, 'EXT-TI-107', 'スキンケア - スタディAI広告1', 'スキンケアに関するtiktok広告', 'TIKTOK', 'PENDING', 'HEALTH', 'https://example.com/ads/tiktok_108.mp4', NULL, '', 90, NULL, NULL, NULL, 'スタディAI', NULL, 'スタディAI', NULL, NULL, NULL, 662876, 11664, '2026-01-21 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "EC"}', '["スキンケア", "tiktok", "health"]', '2026-02-12 23:40:23.56268+00', '2026-02-12 23:40:23.562681+00');
INSERT INTO public.ads VALUES (108, 'EXT-TI-108', 'スキンケア - キャリアナビ広告2', 'スキンケアに関するtiktok広告', 'TIKTOK', 'PENDING', 'APP', 'https://example.com/ads/tiktok_109.mp4', NULL, '', 120, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 3001112, 40444, '2026-01-18 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "記事LP"}', '["スキンケア", "tiktok", "app"]', '2026-02-12 23:40:23.562681+00', '2026-02-12 23:40:23.562682+00');
INSERT INTO public.ads VALUES (109, 'EXT-IN-109', 'スキンケア - ファイナンスワン広告1', 'スキンケアに関するinstagram広告', 'INSTAGRAM', 'PENDING', 'HEALTH', 'https://example.com/ads/instagram_110.mp4', NULL, '', 90, NULL, NULL, NULL, 'ファイナンスワン', NULL, 'ファイナンスワン', NULL, NULL, NULL, 3089221, 16109, '2026-01-21 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "EC"}', '["スキンケア", "instagram", "health"]', '2026-02-12 23:40:23.562682+00', '2026-02-12 23:40:23.562683+00');
INSERT INTO public.ads VALUES (110, 'EXT-IN-110', 'スキンケア - カラーラボ広告2', 'スキンケアに関するinstagram広告', 'INSTAGRAM', 'PENDING', 'GAMING', 'https://example.com/ads/instagram_111.mp4', NULL, '', 90, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 1347203, 10007, '2026-01-20 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "記事LP"}', '["スキンケア", "instagram", "gaming"]', '2026-02-12 23:40:23.562683+00', '2026-02-12 23:40:23.562684+00');
INSERT INTO public.ads VALUES (111, 'EXT-FA-111', 'スキンケア - モバイルセーバー広告1', 'スキンケアに関するfacebook広告', 'FACEBOOK', 'PENDING', 'EDUCATION', 'https://example.com/ads/facebook_112.mp4', NULL, '', 15, NULL, NULL, NULL, 'モバイルセーバー', NULL, 'モバイルセーバー', NULL, NULL, NULL, 1679657, 28124, '2026-02-02 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "facebook", "education"]', '2026-02-12 23:40:23.562684+00', '2026-02-12 23:40:23.562685+00');
INSERT INTO public.ads VALUES (112, 'EXT-FA-112', 'スキンケア - ゲームスタジオX広告2', 'スキンケアに関するfacebook広告', 'FACEBOOK', 'PENDING', 'APP', 'https://example.com/ads/facebook_113.mp4', NULL, '', 60, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 4854677, 76803, '2026-01-16 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "facebook", "app"]', '2026-02-12 23:40:23.562685+00', '2026-02-12 23:40:23.562686+00');
INSERT INTO public.ads VALUES (113, 'EXT-X-113', 'スキンケア - ビューティーラボ広告1', 'スキンケアに関するx_twitter広告', 'X_TWITTER', 'PENDING', 'EDUCATION', 'https://example.com/ads/x_twitter_114.mp4', NULL, '', 15, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 3639606, 20560, '2026-01-24 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "EC"}', '["スキンケア", "x_twitter", "education"]', '2026-02-12 23:40:23.562686+00', '2026-02-12 23:40:23.562687+00');
INSERT INTO public.ads VALUES (114, 'EXT-X-114', 'スキンケア - ゲームスタジオX広告2', 'スキンケアに関するx_twitter広告', 'X_TWITTER', 'PENDING', 'EDUCATION', 'https://example.com/ads/x_twitter_115.mp4', NULL, '', 120, NULL, NULL, NULL, 'ゲームスタジオX', NULL, 'ゲームスタジオX', NULL, NULL, NULL, 1645217, 31295, '2026-01-24 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "x_twitter", "education"]', '2026-02-12 23:40:23.562687+00', '2026-02-12 23:40:23.562687+00');
INSERT INTO public.ads VALUES (115, 'EXT-LI-115', 'スキンケア - ウェルスナビ広告1', 'スキンケアに関するline広告', 'LINE', 'PENDING', 'APP', 'https://example.com/ads/line_116.mp4', NULL, '', 30, NULL, NULL, NULL, 'ウェルスナビ', NULL, 'ウェルスナビ', NULL, NULL, NULL, 847623, 11475, '2026-02-03 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "line", "app"]', '2026-02-12 23:40:23.562688+00', '2026-02-12 23:40:23.562688+00');
INSERT INTO public.ads VALUES (116, 'EXT-LI-116', 'スキンケア - カラーラボ広告2', 'スキンケアに関するline広告', 'LINE', 'PENDING', 'HEALTH', 'https://example.com/ads/line_117.mp4', NULL, '', 30, NULL, NULL, NULL, 'カラーラボ', NULL, 'カラーラボ', NULL, NULL, NULL, 3224249, 49510, '2026-01-19 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "アプリストア"}', '["スキンケア", "line", "health"]', '2026-02-12 23:40:23.562689+00', '2026-02-12 23:40:23.562689+00');
INSERT INTO public.ads VALUES (117, 'EXT-YA-117', 'スキンケア - アニマルケア広告1', 'スキンケアに関するyahoo広告', 'YAHOO', 'PENDING', 'HEALTH', 'https://example.com/ads/yahoo_118.mp4', NULL, '', 15, NULL, NULL, NULL, 'アニマルケア', NULL, 'アニマルケア', NULL, NULL, NULL, 3129837, 50794, '2026-02-10 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "記事LP"}', '["スキンケア", "yahoo", "health"]', '2026-02-12 23:40:23.56269+00', '2026-02-12 23:40:23.56269+00');
INSERT INTO public.ads VALUES (118, 'EXT-YA-118', 'スキンケア - ランゲージテック広告2', 'スキンケアに関するyahoo広告', 'YAHOO', 'PENDING', 'GAMING', 'https://example.com/ads/yahoo_119.mp4', NULL, '', 30, NULL, NULL, NULL, 'ランゲージテック', NULL, 'ランゲージテック', NULL, NULL, NULL, 3418953, 4765, '2026-01-19 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "EC"}', '["スキンケア", "yahoo", "gaming"]', '2026-02-12 23:40:23.56269+00', '2026-02-12 23:40:23.562691+00');
INSERT INTO public.ads VALUES (119, 'EXT-PI-119', 'スキンケア - キャリアナビ広告1', 'スキンケアに関するpinterest広告', 'PINTEREST', 'PENDING', 'FINANCE', 'https://example.com/ads/pinterest_120.mp4', NULL, '', 15, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 1954507, 15803, '2026-02-04 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "アプリストア"}', '["スキンケア", "pinterest", "finance"]', '2026-02-12 23:40:23.562691+00', '2026-02-12 23:40:23.562692+00');
INSERT INTO public.ads VALUES (120, 'EXT-PI-120', 'スキンケア - ナチュラルビューティー広告2', 'スキンケアに関するpinterest広告', 'PINTEREST', 'PENDING', 'HEALTH', 'https://example.com/ads/pinterest_121.mp4', NULL, '', 15, NULL, NULL, NULL, 'ナチュラルビューティー', NULL, 'ナチュラルビューティー', NULL, NULL, NULL, 2972104, 44742, '2026-02-03 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "アプリストア"}', '["スキンケア", "pinterest", "health"]', '2026-02-12 23:40:23.562692+00', '2026-02-12 23:40:23.562693+00');
INSERT INTO public.ads VALUES (121, 'EXT-SM-121', 'スキンケア - スキンケアプラス広告1', 'スキンケアに関するsmartnews広告', 'SMARTNEWS', 'PENDING', 'HEALTH', 'https://example.com/ads/smartnews_122.mp4', NULL, '', 30, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 825512, 16155, '2026-01-21 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "アプリストア"}', '["スキンケア", "smartnews", "health"]', '2026-02-12 23:40:23.562693+00', '2026-02-12 23:40:23.562693+00');
INSERT INTO public.ads VALUES (122, 'EXT-SM-122', 'スキンケア - 京都菓子工房広告2', 'スキンケアに関するsmartnews広告', 'SMARTNEWS', 'PENDING', 'FOOD', 'https://example.com/ads/smartnews_123.mp4', NULL, '', 90, NULL, NULL, NULL, '京都菓子工房', NULL, '京都菓子工房', NULL, NULL, NULL, 4505264, 82460, '2026-01-28 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "EC"}', '["スキンケア", "smartnews", "food"]', '2026-02-12 23:40:23.562694+00', '2026-02-12 23:40:23.562694+00');
INSERT INTO public.ads VALUES (123, 'EXT-GO-123', 'スキンケア - スキンケアプラス広告1', 'スキンケアに関するgoogle_ads広告', 'GOOGLE_ADS', 'PENDING', 'TECHNOLOGY', 'https://example.com/ads/google_ads_124.mp4', NULL, '', 120, NULL, NULL, NULL, 'スキンケアプラス', NULL, 'スキンケアプラス', NULL, NULL, NULL, 1468852, 25305, '2026-02-08 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "google_ads", "technology"]', '2026-02-12 23:40:23.562695+00', '2026-02-12 23:40:23.562695+00');
INSERT INTO public.ads VALUES (124, 'EXT-GO-124', 'スキンケア - 京都菓子工房広告2', 'スキンケアに関するgoogle_ads広告', 'GOOGLE_ADS', 'PENDING', 'GAMING', 'https://example.com/ads/google_ads_125.mp4', NULL, '', 60, NULL, NULL, NULL, '京都菓子工房', NULL, '京都菓子工房', NULL, NULL, NULL, 2574552, 966, '2026-02-10 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "google_ads", "gaming"]', '2026-02-12 23:40:23.562696+00', '2026-02-12 23:40:23.562696+00');
INSERT INTO public.ads VALUES (125, 'EXT-GU-125', 'スキンケア - キャリアナビ広告1', 'スキンケアに関するgunosy広告', 'GUNOSY', 'PENDING', 'EDUCATION', 'https://example.com/ads/gunosy_126.mp4', NULL, '', 15, NULL, NULL, NULL, 'キャリアナビ', NULL, 'キャリアナビ', NULL, NULL, NULL, 3088254, 27469, '2026-01-21 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "直LP"}', '["スキンケア", "gunosy", "education"]', '2026-02-12 23:40:23.562696+00', '2026-02-12 23:40:23.562697+00');
INSERT INTO public.ads VALUES (126, 'EXT-GU-126', 'スキンケア - マネーテック広告2', 'スキンケアに関するgunosy広告', 'GUNOSY', 'PENDING', 'APP', 'https://example.com/ads/gunosy_127.mp4', NULL, '', 120, NULL, NULL, NULL, 'マネーテック', NULL, 'マネーテック', NULL, NULL, NULL, 3618816, 70443, '2026-02-06 23:40:23.557708+00', '2026-02-12 23:40:23.557708+00', '{"crawl_query": "スキンケア", "destination_url": "https://example.com/lp/スキンケア", "destination_type": "EC"}', '["スキンケア", "gunosy", "app"]', '2026-02-12 23:40:23.562697+00', '2026-02-12 23:40:23.562698+00');
INSERT INTO public.ads VALUES (127, 'DEMO-YO-127', 'プロテイン - フィットテック広告1', 'プロテインに関するyoutube広告 (デモデータ)', 'YOUTUBE', 'PENDING', 'GAMING', 'https://example.com/demo/youtube_128.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'フィットテック', NULL, 'フィットテック', NULL, NULL, NULL, 1719349, 44860, '2026-02-02 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "直LP"}', '["プロテイン", "youtube", "demo"]', '2026-02-12 23:46:35.787898+00', '2026-02-12 23:46:35.787902+00');
INSERT INTO public.ads VALUES (128, 'DEMO-YO-128', 'プロテイン - 京都菓子工房広告2', 'プロテインに関するyoutube広告 (デモデータ)', 'YOUTUBE', 'PENDING', 'FOOD', 'https://example.com/demo/youtube_129.mp4', NULL, NULL, 60, NULL, NULL, NULL, '京都菓子工房', NULL, '京都菓子工房', NULL, NULL, NULL, 776091, 18416, '2026-01-19 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "アプリストア"}', '["プロテイン", "youtube", "demo"]', '2026-02-12 23:46:35.787903+00', '2026-02-12 23:46:35.787904+00');
INSERT INTO public.ads VALUES (129, 'DEMO-YO-129', 'プロテイン - モバイルセーバー広告3', 'プロテインに関するyoutube広告 (デモデータ)', 'YOUTUBE', 'PENDING', 'HEALTH', 'https://example.com/demo/youtube_130.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'モバイルセーバー', NULL, 'モバイルセーバー', NULL, NULL, NULL, 2619164, 11905, '2026-02-12 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "記事LP"}', '["プロテイン", "youtube", "demo"]', '2026-02-12 23:46:35.787905+00', '2026-02-12 23:46:35.787908+00');
INSERT INTO public.ads VALUES (130, 'DEMO-TI-130', 'プロテイン - ビューティーラボ広告1', 'プロテインに関するtiktok広告 (デモデータ)', 'TIKTOK', 'PENDING', 'FINANCE', 'https://example.com/demo/tiktok_131.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 387547, 43185, '2026-02-09 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "アプリストア"}', '["プロテイン", "tiktok", "demo"]', '2026-02-12 23:46:35.787909+00', '2026-02-12 23:46:35.78791+00');
INSERT INTO public.ads VALUES (131, 'DEMO-TI-131', 'プロテイン - ファイナンスワン広告2', 'プロテインに関するtiktok広告 (デモデータ)', 'TIKTOK', 'PENDING', 'FINANCE', 'https://example.com/demo/tiktok_132.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'ファイナンスワン', NULL, 'ファイナンスワン', NULL, NULL, NULL, 2244516, 47171, '2026-02-09 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "記事LP"}', '["プロテイン", "tiktok", "demo"]', '2026-02-12 23:46:35.78791+00', '2026-02-12 23:46:35.787911+00');
INSERT INTO public.ads VALUES (132, 'DEMO-TI-132', 'プロテイン - ビューティーラボ広告3', 'プロテインに関するtiktok広告 (デモデータ)', 'TIKTOK', 'PENDING', 'BEAUTY', 'https://example.com/demo/tiktok_133.mp4', NULL, NULL, 30, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 2776877, 5939, '2026-02-09 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "アプリストア"}', '["プロテイン", "tiktok", "demo"]', '2026-02-12 23:46:35.787912+00', '2026-02-12 23:46:35.787913+00');
INSERT INTO public.ads VALUES (133, 'DEMO-IN-133', 'プロテイン - エデュテック広告1', 'プロテインに関するinstagram広告 (デモデータ)', 'INSTAGRAM', 'PENDING', 'FOOD', 'https://example.com/demo/instagram_134.mp4', NULL, NULL, 60, NULL, NULL, NULL, 'エデュテック', NULL, 'エデュテック', NULL, NULL, NULL, 4863288, 21271, '2026-01-25 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "EC"}', '["プロテイン", "instagram", "demo"]', '2026-02-12 23:46:35.787913+00', '2026-02-12 23:46:35.787914+00');
INSERT INTO public.ads VALUES (134, 'DEMO-IN-134', 'プロテイン - ビューティーラボ広告2', 'プロテインに関するinstagram広告 (デモデータ)', 'INSTAGRAM', 'PENDING', 'GAMING', 'https://example.com/demo/instagram_135.mp4', NULL, NULL, 90, NULL, NULL, NULL, 'ビューティーラボ', NULL, 'ビューティーラボ', NULL, NULL, NULL, 2641541, 48782, '2026-02-08 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "記事LP"}', '["プロテイン", "instagram", "demo"]', '2026-02-12 23:46:35.787915+00', '2026-02-12 23:46:35.787915+00');
INSERT INTO public.ads VALUES (135, 'DEMO-IN-135', 'プロテイン - エンタメプラス広告3', 'プロテインに関するinstagram広告 (デモデータ)', 'INSTAGRAM', 'PENDING', 'EC_D2C', 'https://example.com/demo/instagram_136.mp4', NULL, NULL, 15, NULL, NULL, NULL, 'エンタメプラス', NULL, 'エンタメプラス', NULL, NULL, NULL, 4793187, 3150, '2026-01-25 23:46:35.736079+00', '2026-02-12 23:46:35.736079+00', '{"is_demo": true, "crawl_query": "プロテイン", "destination_url": "https://example.com/lp/プロテイン", "destination_type": "EC"}', '["プロテイン", "instagram", "demo"]', '2026-02-12 23:46:35.787916+00', '2026-02-12 23:46:35.787917+00');


--
-- Data for Name: ad_analyses; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: ad_classification_tags; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: ad_daily_metrics; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: ad_embeddings; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: ad_fatigue_logs; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: ad_frames; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.alembic_version VALUES ('001');


--
-- Data for Name: alert_logs; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: landing_pages; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: appeal_axis_analyses; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.users VALUES (1, 'admin@vaap.com', '$2b$12$C/d5RjyHOWn7bhpBp64qvugspcJr2nf.2vbSJ0VDWVKvFIR75A6Mq', 'Admin', 'ADMIN', true, NULL, NULL, '2026-02-12 23:59:17.194569+00', '2026-02-12 23:59:17.194573+00');


--
-- Data for Name: campaigns; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: campaign_ads; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: cpm_calibrations; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: creative_templates; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: detected_objects; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: lp_funnels; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: funnel_steps; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: generated_creatives; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: lp_analyses; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: lp_fingerprints; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: lp_sections; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: notification_configs; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: performance_predictions; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: platform_api_keys; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: product_rankings; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: saved_items; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: scene_boundaries; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: sentiment_results; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: spend_estimates; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: text_detections; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: transcriptions; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: trend_predictions; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Data for Name: usp_patterns; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Name: ad_analyses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ad_analyses_id_seq', 1, false);


--
-- Name: ad_classification_tags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ad_classification_tags_id_seq', 1, false);


--
-- Name: ad_daily_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ad_daily_metrics_id_seq', 1, false);


--
-- Name: ad_embeddings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ad_embeddings_id_seq', 1, false);


--
-- Name: ad_fatigue_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ad_fatigue_logs_id_seq', 1, false);


--
-- Name: ad_frames_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ad_frames_id_seq', 1, false);


--
-- Name: ads_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ads_id_seq', 135, true);


--
-- Name: alert_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.alert_logs_id_seq', 1, false);


--
-- Name: appeal_axis_analyses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.appeal_axis_analyses_id_seq', 1, false);


--
-- Name: campaign_ads_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.campaign_ads_id_seq', 1, false);


--
-- Name: campaigns_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.campaigns_id_seq', 1, false);


--
-- Name: cpm_calibrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.cpm_calibrations_id_seq', 1, false);


--
-- Name: creative_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.creative_templates_id_seq', 1, false);


--
-- Name: detected_objects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.detected_objects_id_seq', 1, false);


--
-- Name: funnel_steps_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.funnel_steps_id_seq', 1, false);


--
-- Name: generated_creatives_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.generated_creatives_id_seq', 1, false);


--
-- Name: landing_pages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.landing_pages_id_seq', 1, false);


--
-- Name: lp_analyses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.lp_analyses_id_seq', 1, false);


--
-- Name: lp_fingerprints_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.lp_fingerprints_id_seq', 1, false);


--
-- Name: lp_funnels_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.lp_funnels_id_seq', 1, false);


--
-- Name: lp_sections_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.lp_sections_id_seq', 1, false);


--
-- Name: notification_configs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.notification_configs_id_seq', 1, false);


--
-- Name: performance_predictions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.performance_predictions_id_seq', 1, false);


--
-- Name: platform_api_keys_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.platform_api_keys_id_seq', 1, true);


--
-- Name: product_rankings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.product_rankings_id_seq', 1, false);


--
-- Name: saved_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.saved_items_id_seq', 1, false);


--
-- Name: scene_boundaries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.scene_boundaries_id_seq', 1, false);


--
-- Name: sentiment_results_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.sentiment_results_id_seq', 1, false);


--
-- Name: spend_estimates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.spend_estimates_id_seq', 1, false);


--
-- Name: text_detections_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.text_detections_id_seq', 1, false);


--
-- Name: transcriptions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.transcriptions_id_seq', 1, false);


--
-- Name: trend_predictions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.trend_predictions_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.users_id_seq', 1, true);


--
-- Name: usp_patterns_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.usp_patterns_id_seq', 1, false);


--
-- PostgreSQL database dump complete
--

\unrestrict yms6b821oZOpWEqrMRy5zpnIUVjkLHJzYHNFeo837kplYqECWEVj6mG30sIS8PM

