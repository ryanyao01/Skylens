import { NativeTabs } from "expo-router/unstable-native-tabs";

import { colors } from "@/constants/theme";

export default function AppTabs() {
  return (
    <NativeTabs
      backgroundColor={colors.tabBar.background}
      indicatorColor={colors.tabBar.indicator}
      labelStyle={{
        default: { color: colors.tabBar.inactive },
        selected: { color: colors.tabBar.active },
      }}
      iconColor={{
        default: colors.tabBar.inactive,
        selected: colors.tabBar.activeIcon,
      }}
      rippleColor="transparent"
    >
      <NativeTabs.Trigger name="globe">
        <NativeTabs.Trigger.Label>GLOBE</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon
          src={require("@/assets/tabIcons/globe.png")}
          renderingMode="template"
        />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>AR VIEW</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon
          src={require("@/assets/tabIcons/airview.png")}
          renderingMode="template"
        />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="deepDive">
        <NativeTabs.Trigger.Label>DEEP DIVE</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon
          src={require("@/assets/tabIcons/deepdive.png")}
          renderingMode="template"
        />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
