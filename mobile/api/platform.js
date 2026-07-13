import { Platform } from 'react-native';

export const isIOS = Platform.OS === 'ios';
export const isAndroid = Platform.OS === 'android';
export const isWeb = Platform.OS === 'web';

export const getDeviceDetails = () => {
  return {
    os: Platform.OS,
    version: Platform.Version,
  };
};
