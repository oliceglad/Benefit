import { useState } from 'react'

type StageStatus = 'completed' | 'current' | 'upcoming'
type StageLane = 'main' | 'interview' | 'assignment'

type HiringStage = {
  id: string
  title: string
  status: StageStatus
  lane: StageLane
  description: string
  participants: string
}

const statusLabels: Record<StageStatus, string> = {
  completed: 'Пройдено',
  current: 'Текущий этап',
  upcoming: 'Впереди',
}

const laneLabels: Record<StageLane, string> = {
  main: 'Основной маршрут',
  interview: 'Интервью',
  assignment: 'Задание · опционально',
}

// A local design fixture, not an employer workflow or a source of hiring decisions.
const currentStage: HiringStage = {
  id: 'team',
  title: 'Обсуждение с командой',
  status: 'current',
  lane: 'main',
  description: 'Кандидат знакомится с будущей командой: обсуждает задачи, ожидания и формат совместной работы.',
  participants: 'Кандидат и команда',
}

const exampleStages: HiringStage[] = [
  {
    id: 'invitation',
    title: 'Приглашение принято',
    status: 'completed',
    lane: 'main',
    description: 'Кандидат изучил условия приглашения и согласился начать общение с компанией.',
    participants: 'Кандидат и рекрутер',
  },
  {
    id: 'intro',
    title: 'Знакомство с рекрутером',
    status: 'completed',
    lane: 'main',
    description: 'Первый разговор о роли, опыте кандидата и взаимных ожиданиях. После него могут идти параллельные этапы оценки.',
    participants: 'Кандидат и рекрутер',
  },
  {
    id: 'technical',
    title: 'Техническое интервью',
    status: 'completed',
    lane: 'interview',
    description: 'Обсуждение практического опыта и подхода к решению задач с техническим специалистом команды.',
    participants: 'Кандидат и технический специалист',
  },
  {
    id: 'assignment',
    title: 'Практическое задание',
    status: 'completed',
    lane: 'assignment',
    description: 'Отдельная ветка для задания, если оно согласовано сторонами. В этом примере результат уже обсуждён; обязательность этапа не задаётся.',
    participants: 'Кандидат и технический специалист',
  },
  currentStage,
  {
    id: 'decision',
    title: 'Обратная связь и решение',
    status: 'upcoming',
    lane: 'main',
    description: 'Результаты обсуждений собираются в общем маршруте. Компания и кандидат обмениваются обратной связью и решают, продолжать ли процесс.',
    participants: 'Кандидат, рекрутер и команда',
  },
  {
    id: 'offer',
    title: 'Оффер',
    status: 'upcoming',
    lane: 'main',
    description: 'Если стороны готовы продолжить, они обсуждают предложение и согласуют условия работы.',
    participants: 'Кандидат и компания',
  },
  {
    id: 'start',
    title: 'Выход в команду',
    status: 'upcoming',
    lane: 'main',
    description: 'После согласования предложения стороны определяют дату начала работы и первые шаги в команде.',
    participants: 'Кандидат и команда',
  },
]

export function HiringJourneyPreview() {
  const [selectedStage, setSelectedStage] = useState(currentStage)
  const completedCount = exampleStages.filter((stage) => stage.status === 'completed').length

  return (
    <section id="hiring-journey" className="hiring-journey company-glass-panel" aria-labelledby="hiring-journey-heading">
      <header className="journey-heading">
        <div>
          <p className="journey-kicker">Пример процесса · Backend-разработчик</p>
          <h2 id="hiring-journey-heading">Этапы найма</h2>
          <p>Путь кандидата с параллельными ветками оценки.</p>
        </div>
        <span className="journey-example-label">Тестовый сценарий</span>
      </header>

      <div className="journey-layout">
        <div className="journey-map">
          <div className="journey-map-caption">
            <span>Прохождение этапов</span>
            <span>{completedCount} из {exampleStages.length} пройдено</span>
          </div>

          <div className="journey-graph">
            <svg className="journey-edges" viewBox="0 0 104 448" preserveAspectRatio="none" aria-hidden="true" focusable="false">
              <path className="journey-edge-main" d="M20 28V252" />
              <path className="journey-edge-interview" d="M20 84C20 112 48 112 48 140V224Q48 252 20 252" />
              <path className="journey-edge-assignment" d="M20 84C20 112 76 112 76 140V224Q76 252 20 252" />
              <path className="journey-edge-upcoming" d="M20 252V420" />
            </svg>
            <ol aria-label="Этапы процесса найма">
              {exampleStages.map((stage, index) => (
                <li key={stage.id}>
                  <button
                    type="button"
                    className={`journey-stage journey-stage-${stage.status}`}
                    aria-pressed={selectedStage.id === stage.id}
                    aria-controls="hiring-stage-detail"
                    onClick={() => setSelectedStage(stage)}
                  >
                    <span className={`journey-node-track journey-lane-${stage.lane}`} aria-hidden="true"><span className="journey-node" /></span>
                    <span className="journey-stage-copy"><span className="journey-stage-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><span className="journey-stage-title">{stage.title}</span></span>
                    <span className="journey-stage-status">{statusLabels[stage.status]}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>

          <div className="journey-legend" aria-label="Ветки процесса">
            <span><i className="journey-legend-main" aria-hidden="true" />Основной маршрут</span>
            <span><i className="journey-legend-interview" aria-hidden="true" />Интервью</span>
            <span><i className="journey-legend-assignment" aria-hidden="true" />Задание</span>
          </div>
        </div>

        <div id="hiring-stage-detail" className="journey-detail" role="region" aria-label="Сведения об этапе" aria-live="polite" aria-atomic="true">
          <p className="journey-detail-label">Выбранный этап</p>
          <h3>{selectedStage.title}</h3>
          <span className={`journey-detail-status journey-detail-status-${selectedStage.status}`}>{statusLabels[selectedStage.status]}</span>
          <p className="journey-detail-description">{selectedStage.description}</p>
          <dl>
            <div><dt>Ветка</dt><dd>{laneLabels[selectedStage.lane]}</dd></div>
            <div><dt>Участники</dt><dd>{selectedStage.participants}</dd></div>
          </dl>
          <p className="journey-detail-hint">Выберите узел или строку в графе, чтобы посмотреть другой этап.</p>
        </div>
      </div>

      <p className="journey-disclaimer">Этапы и статусы приведены для оценки интерфейса. Это пример, а не история реального кандидата.</p>
    </section>
  )
}
