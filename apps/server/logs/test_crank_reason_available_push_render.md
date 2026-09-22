# 用例 test_crank_reason_available_push_render

- 执行时间：2026-09-21 22:04:02
- 请求次数：1

## 请求 1 · POST /api/testProcessor

- URL：http://10.118.70.249:8080/api/testProcessor
- 状态码：200
- 耗时：0.203s

### 请求头

```json
{
  "host": "10.118.70.249:8080",
  "accept-encoding": "gzip, deflate, br, zstd",
  "connection": "keep-alive",
  "user-agent": "python-httpx/0.28.1",
  "content-type": "application/json",
  "accept": "application/json, */*",
  "content-length": "591"
}
```

### 请求报文

```json
{
  "module": "content",
  "event": "default",
  "scenario": "realtime",
  "uid": "test-crank-s1-001",
  "locale": "zh-TW",
  "requestId": "pytest-test-crank-s1-001",
  "triggerEventJson": "{\"eventType\": \"T0\"}",
  "experimentContextJson": "{\"experimentVersion\": \"H\"}",
  "reRankingContextJson": "{\"selection\": {\"recallType\": \"HOTEL_ITEM\", \"prdType\": \"H\", \"hotelId\": 59508, \"cityId\": 2, \"checkIn\": \"2026-09-22\", \"checkOut\": \"2026-09-24\", \"recallScene\": \"CROSS_SELL\", \"hotelBenefitType\": \"PRICE_MATCH\", \"hotelBenefitLinkUrl\": \"https://m.ctrip.com/webapp/hotel/hoteldetail/59508.html\"}}"
}
```

### 响应报文

```json
{
  "ResponseStatus": {
    "Timestamp": "/Date(1789999441602+0800)/",
    "Ack": "Success",
    "Errors": [],
    "Extension": [
      {
        "ContentType": "CAT_MESSAGE_ID",
        "Value": "100056585-0a7646f9-497222-569"
      }
    ]
  },
  "success": true,
  "errorCode": "20000",
  "errorMessage": "Success",
  "resultJson": "{\"requestId\":\"pytest-test-crank-s1-001\",\"uid\":\"test-crank-s1-001\",\"locale\":\"zh-TW\",\"qmqMessageTiming\":null,\"triggerEvent\":{\"eventType\":\"T0\",\"triggerSource\":null,\"occurredAt\":null,\"uid\":null,\"locale\":null},\"evaluationTimeMillis\":1789999441441,\"selection\":{\"eventType\":\"T0\",\"executionId\":\"t0_price_match_crank\",\"executionPolicy\":{\"feature\":{\"event\":\"CROSS_SELL_FEATURE\"},\"recall\":{\"event\":\"CROSS_SELL_RECALL\",\"hotelFallback\":{\"T0\":\"post_exit_v1\",\"T1\":\"next_day_v1\"},\"browsingMaxPerProduct\":10},\"ranking\":{\"event\":\"CROSS_SELL_RANKING\",\"strategyId\":null},\"itemEnrich\":{\"event\":\"HOTEL_ITEM_ENRICH\"},\"delivery\":{\"channels\":[\"PUSH\",\"WHATSAPP\"]},\"params\":{\"tag.push_template_group\":\"crank\"}},\"expCode\":\"260831_IBU_AgenticV2\",\"version\":\"H\",\"testVersionOverride\":true},\"featureContext\":{\"userProfile\":null,\"behaviorSequence\":{},\"currencyFeature\":{\"currency\":null,\"source\":\"NONE\"},\"memberBenefitFeature\":{\"hotelMemberBenefitType\":\"NONE\"},\"itineraryFeature\":null},\"recallContext\":{\"strategyId\":null,\"candidates\":[]},\"rankingContext\":{\"strategyId\":null,\"rankedCandidates\":[],\"scoredItems\":null},\"itemEnrichContext\":{\"candidates\":[]},\"reRankingContext\":{\"selection\":{\"recallType\":\"HOTEL_ITEM\",\"prdType\":\"H\",\"cityTravelPurpose\":\"Other\",\"recallScene\":\"CROSS_SELL\",\"primarySource\":null,\"allSources\":[],\"tripId\":null,\"score\":null,\"primaryStrategy\":null,\"allStrategies\":[],\"itineraryStatus\":null,\"leadTime\":null,\"cityId\":2,\"checkIn\":\"2026-09-22\",\"checkOut\":\"2026-09-24\",\"hotelId\":59508,\"hotelBenefitType\":\"PRICE_MATCH\",\"hotelBenefitValue\":null,\"priceWithCurrency\":null},\"filteredCandidates\":null},\"contentContext\":{\"creativeItems\":[{\"channelType\":\"PUSH\",\"contentBaseId\":20574,\"contentDetailId\":384833,\"title\":\"📍 去上海住邊好？--字段为地鐵站步行3分鐘\",\"subTitle\":\"✨你睇過嘅5780北京軍都之家飯店(北京昌平捷運站商業街店)入選北京 20 大精選商務飯店。地鐵站步行3分鐘，行程未定不妨先收藏。\",\"link\":\"https://m.ctrip.com/webapp/hotel/hoteldetail/59508.html\",\"imageUrl\":\"https://ak-d.tripcdn.com/images/0a12v12000b645ltiA354_D_250_250.png\",\"bigImageUrl\":\"\"}],\"templateContext\":{\"tagFacts\":[{\"tagKey\":\"prd_type\",\"value\":\"H\"},{\"tagKey\":\"trigger_timing\",\"value\":\"T0\"},{\"tagKey\":\"travel_purpose\",\"value\":\"Other\"},{\"tagKey\":\"coupon_available\",\"value\":\"false\"},{\"tagKey\":\"hotel_benefit_type\",\"value\":\"PRICE_MATCH\"},{\"tagKey\":\"recall_granularity\",\"value\":\"item\"},{\"tagKey\":\"business_scenario\",\"value\":\"cross_sell\"},{\"tagKey\":\"crank_reason_available\",\"value\":\"true\"},{\"tagKey\":\"push_template_group\",\"value\":\"crank\"}],\"attemptedChannels\":[\"PUSH\"],\"selectedCandidates\":{\"PUSH\":{\"channelType\":\"PUSH\",\"contentBaseId\":20574,\"contentDetailId\":384833,\"priority\":7,\"randomEnable\":1,\"renderVarSnapshot\":{\"hotelName\":\"5780北京軍都之家飯店(北京昌平捷運站商業街店)\",\"hotel_name\":\"5780北京軍都之家飯店(北京昌平捷運站商業街店)\",\"hotelname\":\"5780北京軍都之家飯店(北京昌平捷運站商業街店)\",\"cityName\":\"上海\",\"citynameofhotel\":\"上海\",\"cityname\":\"上海\",\"city_name\":\"上海\",\"acityname\":\"上海\",\"aCityName\":\"上海\",\"hotelImageUrl\":\"https://ak-d.tripcdn.com/images/0a12v12000b645ltiA354_D_250_250.png\",\"hotelBenefitLinkUrl\":\"https://m.ctrip.com/webapp/hotel/hoteldetail/59508.html\",\"titleWithDistrict\":\"北京 20 大精選商務飯店\",\"recommendReason\":\"地鐵站步行3分鐘\"},\"renderedItemIds\":[]}},\"matchedBindingIds\":[10053,13448,20574],\"eliminations\":[],\"failureStage\":null},\"benefitSnapshot\":null,\"hotelCustomerType\":null},\"channelContext\":{\"countryCode\":null,\"phoneNo\":null,\"subscriptionAction\":null,\"deliveryResults\":{},\"suppressedChannels\":{},\"allChannelsSuppressed\":false}}",
  "costTimeMs": 161
}
```
