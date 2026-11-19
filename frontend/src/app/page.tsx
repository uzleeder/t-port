import { AIPlannerShowcase } from "@/components/landing/AIPlannerShowcase";
import { CinematicHero } from "@/components/landing/CinematicHero";
import { ExploreUzbekistan } from "@/components/landing/ExploreUzbekistan";
import { FeatureBento } from "@/components/landing/FeatureBento";
import { FinalCTA } from "@/components/landing/FinalCTA";
import { GlobalVision } from "@/components/landing/GlobalVision";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { IntroAnimation } from "@/components/landing/IntroAnimation";
import { TransportSearch } from "@/components/landing/TransportSearch";
import { DemoNotice } from "@/components/Notices";
import { RecentSearches } from "@/components/RecentSearches";
import { T } from "@/components/T";

/**
 * Public landing page: the gateway to the T-PORT app. Every section is wired to the real app:
 * search, the 14 regions and their places, T-AI, accounts. Text is in English, Uzbek and Russian.
 */
export default function Home() {
  return (
    <div className="px-4 sm:px-8 lg:px-0">
      <IntroAnimation />
      <CinematicHero />

      <section id="search" aria-labelledby="search-h" className="relative z-10 mx-auto -mt-32 max-w-6xl scroll-mt-28 sm:-mt-36 lg:-mt-44">
        <h2 id="search-h" className="sr-only">
          <T k="search.submit" />
        </h2>
        <TransportSearch />
        <div className="mt-4 space-y-4">
          <DemoNotice />
          <RecentSearches />
        </div>
      </section>

      <div className="mx-auto max-w-[94rem] space-y-28 py-24 sm:space-y-36 sm:py-32">
        <ExploreUzbekistan />
        <AIPlannerShowcase />
        <HowItWorks />
        <FeatureBento />
      </div>

      <GlobalVision />
      <FinalCTA />
    </div>
  );
}
