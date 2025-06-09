import { api } from './client';

export interface ScrapeTask {
  task_id: string;
  status: 'started' | 'running' | 'completed' | 'error' | 'not_found' | 'already_running';
  details?: {
    started_at?: string;
    scraper?: string;
    max_pages?: number;
    status_url?: string;
    message?: string;
    progress?: number; // Added progress property
  };
  result?: {
    created: number;
    updated: number;
    total: number;
  };
  error?: string;
}

export const scraperApi = {
  /**
   * Trigger a new scraping task
   * @param maxPages Maximum number of pages to scrape (default: 5)
   */
  async startScraping(maxPages: number = 5): Promise<ScrapeTask> {
    const response = await api.post(`/scrape/yad2?max_pages=${maxPages}`);
    return response.data;
  },

  /**
   * Get the status of a scraping task
   * @param taskId The ID of the task to check
   */
  async getStatus(taskId: string): Promise<ScrapeTask> {
    const response = await api.get(`/scrape/status/${taskId}`);
    return response.data;
  },

  /**
   * List all active scraping tasks
   */
  async listTasks(): Promise<{
    count: number;
    tasks: Array<{
      task_id: string;
      status: string;
      done: boolean;
      cancelled: boolean;
    }>;
  }> {
    const response = await api.get('/scrape/tasks');
    return response.data;
  },

  /**
   * Poll the status of a task until it completes or fails
   * @param taskId The ID of the task to poll
   * @param interval Polling interval in milliseconds (default: 1000)
   * @param timeout Maximum time to wait in milliseconds (default: 300000 = 5 minutes)
   */
  async pollTask(
    taskId: string,
    interval: number = 1000,
    timeout: number = 300000
  ): Promise<ScrapeTask> {
    const startTime = Date.now();
    
    return new Promise((resolve, reject) => {
      const checkStatus = async () => {
        try {
          // Check if we've exceeded the timeout
          if (Date.now() - startTime > timeout) {
            reject(new Error('Polling timeout exceeded'));
            return;
          }
          
          const status = await this.getStatus(taskId);
          
          // If the task is done, resolve with the result
          if (['completed', 'error', 'not_found'].includes(status.status)) {
            resolve(status);
            return;
          }
          
          // Otherwise, check again after the interval
          setTimeout(checkStatus, interval);
        } catch (error) {
          reject(error);
        }
      };
      
      // Start polling
      checkStatus();
    });
  },
};
