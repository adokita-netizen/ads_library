import type { ComponentProps } from "react";
import ProRankingTable from "@/components/dashboard/ProRankingTable";
import { CreativeViewer } from "@/components/common/CreativeViewer";

const onAdSelect = (_adId: number) => {};

const validProRankingProps: ComponentProps<typeof ProRankingTable> = {
  onAdSelect,
  viewMode: "table",
  adFormat: "video",
  isAffiliate: "true",
  advancedFilters: {
    videoFormat: "video",
    excludedAdvertisers: [],
    excludedDomains: [],
    dateRange: { from: null, to: null },
    viewCountMin: null,
    viewCountMax: 1000000,
    likeCountMin: null,
    likeCountMax: null,
    destinationType: null,
    destinationDomain: null,
    spendMin: null,
    spendMax: null,
  },
};

const validCreativeViewerProps: ComponentProps<typeof CreativeViewer> = {
  adId: 123,
  creativeType: "video",
  imageUrl: "https://example.com/image.jpg",
  videoUrl: "https://example.com/video.mp4",
  carouselUrls: ["https://example.com/1.jpg", "https://example.com/2.jpg"],
  extractionStatus: "completed",
};

void validProRankingProps;
void validCreativeViewerProps;

// Valid JSX usage must compile.
<ProRankingTable onAdSelect={onAdSelect} viewMode="gallery" />;
<CreativeViewer adId={1} creativeType="image" />;

// Invalid values should fail type checks.
// @ts-expect-error ProRankingTable viewMode is restricted to table/card/gallery.
<ProRankingTable onAdSelect={onAdSelect} viewMode="list" />;

// @ts-expect-error ProRankingTable isAffiliate accepts only all/true/false.
<ProRankingTable onAdSelect={onAdSelect} isAffiliate="yes" />;

// @ts-expect-error ProRankingTable requires onAdSelect.
<ProRankingTable />;

// @ts-expect-error CreativeViewer adId must be number or null.
<CreativeViewer adId="123" />;

// @ts-expect-error CreativeViewer carouselUrls must be string[].
<CreativeViewer carouselUrls={[1, 2, 3]} />;

export {};
