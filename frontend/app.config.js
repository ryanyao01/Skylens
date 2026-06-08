export default ({ config }) => {
  // Filter out any existing 'react-native-maps' plugin from app.json
  const plugins = config.plugins || [];
  const filteredPlugins = plugins.filter(
    (p) =>
      p !== "react-native-maps" &&
      (Array.isArray(p) ? p[0] !== "react-native-maps" : true),
  );

  // Inject the fully configured plugin using the environment variable
  filteredPlugins.push([
    "react-native-maps",
    {
      androidGoogleMapsApiKey: process.env.GOOGLE_MAPS_API_KEY,
    },
  ]);

  return {
    ...config,
    plugins: filteredPlugins,
  };
};
