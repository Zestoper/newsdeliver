export const AGE_GROUPS = [
  { key: 'teen', label: '10~20대' },
  { key: 'adult', label: '30~40대' },
  { key: 'senior', label: '50~70대' },
] as const

export type AgeGroup = (typeof AGE_GROUPS)[number]['key']

export const AGE_TAGS: Record<AgeGroup, { label: string; keyword: string }[]> = {
  teen: [
    { label: '취업/채용', keyword: '취업' },
    { label: 'IT/AI', keyword: 'IT' },
    { label: '연예/문화', keyword: '연예' },
    { label: '게임/e스포츠', keyword: '게임' },
    { label: '패션/뷰티', keyword: '패션' },
    { label: 'SNS/트렌드', keyword: 'SNS' },
    { label: '대학/교육', keyword: '대학' },
    { label: '주식입문', keyword: '주식' },
    { label: '사회이슈', keyword: '사회' },
    { label: '해외화제', keyword: '해외' },
  ],
  adult: [
    { label: '경제/부동산', keyword: '부동산' },
    { label: '주식/재테크', keyword: '재테크' },
    { label: '육아/교육', keyword: '육아' },
    { label: '건강/의료', keyword: '건강' },
    { label: '자동차', keyword: '자동차' },
    { label: '정치/사회', keyword: '정치' },
    { label: 'IT/업무', keyword: 'IT' },
    { label: '창업/비즈니스', keyword: '창업' },
    { label: '여행/레저', keyword: '여행' },
    { label: '생활정보', keyword: '생활' },
  ],
  senior: [
    { label: '건강/의료', keyword: '건강' },
    { label: '정치', keyword: '정치' },
    { label: '경제', keyword: '경제' },
    { label: '부동산', keyword: '부동산' },
    { label: '연금/복지', keyword: '연금' },
    { label: '사회/시사', keyword: '사회' },
    { label: '생활정보', keyword: '생활' },
    { label: '문화/전통', keyword: '문화' },
    { label: '여행', keyword: '여행' },
    { label: '지역뉴스', keyword: '지역' },
  ],
}
