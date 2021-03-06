from __future__ import division, print_function

import numpy as np

from canonical_system import CanonicalSystem
from obstacle import Obstacle
from repulsive import Ct, Ct_coupling

# test
from tqdm import tqdm
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as p3
import matplotlib.animation as animation
from attractive import Att
import matplotlib.patches as mpatches


class PositionDMP():
    def __init__(self, n_bfs=10, alpha=48.0, beta=None, cs_alpha=None, cs=None, obstacles=None):
        self.n_bfs = n_bfs
        self.alpha = alpha
        self.beta = beta if beta is not None else self.alpha / 4
        self.cs = cs if cs is not None else CanonicalSystem(alpha=cs_alpha if cs_alpha is not None else self.alpha/2)

        # Centres of the Gaussian basis functions
        self.c = np.exp(-self.cs.alpha * np.linspace(0, 1, self.n_bfs))

        # Variance of the Gaussian basis functions
        self.h = 1.0 / np.gradient(self.c)**2

        # Scaling factor
        self.Dp = np.identity(3)

        # Initially weights are zero (no forcing term)
        self.w = np.zeros((3, self.n_bfs))

        # Initial- and goal positions
        self.p0 = np.zeros(3)
        self.gp = np.zeros(3)

        self.obstacles = obstacles

        self.reset()

    def step(self, x, dt, tau, x_target=None):
        def fp(xj):
            psi = np.exp(-self.h * (xj - self.c)**2)
            return self.Dp.dot(self.w.dot(psi) / psi.sum() * xj)

        # DMP system acceleration
        # TODO: Implement the transformation system differential equation for the acceleration, given that you know the
        # values of the following variables:
        # self.alpha, self.beta, self.gp, self.p, self.dp, tau, x

        ###### OLD ######
        #sphere  = Obstacle([0.575, 0.30, 0.45])
        #sphere = Obstacle([0., 0.25, 0.80])
        ###### NEW ######
        if x_target is None:
            self.ddp = (self.alpha*( self.beta * (self.gp - self.p) - tau*self.dp ) + fp(x) + Ct_coupling(self.p, self.dp, self.obstacles) )/(tau*tau)
        else:
            self.ddp = (self.alpha*( self.beta * (self.gp - self.p) - tau*self.dp ) + fp(x) + Ct_coupling(self.p, self.dp, self.obstacles) + Att(x_target, self.p, self.obstacles.pos) )/(tau*tau)

        # Integrate acceleration to obtain velocity
        self.dp += self.ddp * dt

        # Integrate velocity to obtain position
        self.p += self.dp * dt

        return self.p, self.dp, self.ddp

    def rollout_moving_obstacle(self, ts, tau, obs_traj, start_obs_mov, demo_p, acctractor_term=False):
        self.reset()
        if np.isscalar(tau):
            tau = np.full_like(ts, tau)

        x = self.cs.rollout(ts, tau)  # Integrate canonical system
        dt = np.gradient(ts) # Differential time vector

        n_steps = len(ts)

        # Generating the points for both obstacle and DMP
        dmp_p = np.empty((n_steps, 3))
        obs_p = []
        obs_p.append((self.obstacles.x, self.obstacles.y, self.obstacles.z))
        if acctractor_term:
            for i in range(n_steps):
                dmp_p[i], _, _ = self.step(x[i], dt[i], tau[i], demo_p[i]) # Remove demo_p[i] for not using attractor field. 
                
                # Moving obstacle
                # First moving obstacle at index DMP
                if i > start_obs_mov:
                    stop_mov = self.obstacles.move_sphere(obs_traj)
                    if not stop_mov:
                        obs_p.append((self.obstacles.x, self.obstacles.y, self.obstacles.z))
        else:
            for i in range(n_steps):
                dmp_p[i], _, _ = self.step(x[i], dt[i], tau[i]) 
                
                # Moving obstacle
                # First moving obstacle at index DMP
                if i > start_obs_mov:
                    stop_mov = self.obstacles.move_sphere(obs_traj)
                    if not stop_mov:
                        obs_p.append((self.obstacles.x, self.obstacles.y, self.obstacles.z))
            
        return dmp_p, obs_p

    def move_and_plot_dmp_obs(self, demo_p, ts, tau, obs_traj, start_obs_mov):
        n_steps = len(ts)
        dmp_p, obs_p = self.rollout_moving_obstacle(ts, tau, obs_traj, start_obs_mov, demo_p)

        def animate3D(i, plot_dmp, dmp_points, plot_obs, obs_points, update_bar):
            # Updating progress bar
            update_bar(1)
            # Plotting DMP
            plot_dmp.set_data(dmp_points[0:i+1,0], dmp_points[0:i+1,1])
            plot_dmp.set_3d_properties(dmp_points[0:i+1,2])

            # Plotting obstacle
            
            if (len(obs_points) - 2 > self.obs_plt_indx) and (i > start_obs_mov): # Showing with magma color while moving and without when not
                plot_obs[0].remove()
                plot_obs[0] = ax.plot_surface(obs_points[self.obs_plt_indx][0], obs_points[self.obs_plt_indx][1], obs_points[self.obs_plt_indx][2], cmap="magma")
                self.obs_plt_indx += 1
            elif (len(obs_points) - 1 > self.obs_plt_indx) and (i > start_obs_mov):
                plot_obs[0].remove()
                plot_obs[0] = ax.plot_surface(obs_points[self.obs_plt_indx][0], obs_points[self.obs_plt_indx][1], obs_points[self.obs_plt_indx][2], rstride=1, cstride=1)
                self.obs_plt_indx += 1

        
        def animate2D(i, t, plt_dmp_x, plt_dmp_y, plt_dmp_z, plt_error, dmp_points, update_bar):
            update_bar(1)
            plt_dmp_x.set_data(t[0:i+1], dmp_points[0:i+1, 0])
            plt_dmp_y.set_data(t[0:i+1], dmp_points[0:i+1, 1])
            plt_dmp_z.set_data(t[0:i+1], dmp_points[0:i+1, 2])
            
            plt_error.set_data(t[0:i+1], np.linalg.norm(demo_p[0:i+1,:] - dmp_points[0:i+1,:], axis=1) )


        with tqdm(total=n_steps) as tbar:
            # Animation of 3D path
            fig = plt.figure()
            ax = p3.Axes3D(fig)

            # Static plots and settings
            # ax.set_xlim(0, 1.2)
            # ax.set_ylim(0, 1.2)
            # ax.set_zlim(0, 1.2)
            ax.view_init(elev=12, azim=-160)
            ax.plot3D(demo_p[:, 0], demo_p[:, 1], demo_p[:, 2], label='Demonstration')

            plot_dmp = ax.plot3D([], [], [])[0]
            plot_obs = [ax.plot_surface(obs_p[0][0], obs_p[0][1], obs_p[0][2], rstride=1, cstride=1)]
            self.obs_plt_indx = 0
           
            ani = animation.FuncAnimation(fig, animate3D, fargs=[plot_dmp, dmp_p, plot_obs, obs_p, tbar.update], frames=n_steps-1, interval=25, blit=False, repeat=False)
            
            # Set up formatting for the movie files
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=60, bitrate=2000)
            ani.save('3D_ori_param.mp4', writer=writer)
            #plt.show()

        with tqdm(total=n_steps) as tbar:
            max_error = np.max(np.linalg.norm(demo_p - dmp_p, axis=1))
            print("Max error",max_error)
            # Animation of 2D path
            fig, axs = plt.subplots(4, 1, sharex=True)
            t = np.arange(0, tau, 0.002)

            axs[0].set_xlabel('t (s)')
            axs[0].set_ylabel('X (m)')
            axs[0].plot(t, demo_p[:, 0], label='Demonstration')
            plt_dmp_x, = axs[0].plot([], [], label='DMP')
            
            axs[1].set_xlabel('t (s)')
            axs[1].set_ylabel('Y (m)')
            axs[1].plot(t, demo_p[:, 1], label='Demonstration')
            plt_dmp_y, = axs[1].plot([], [], label='DMP')
            
            axs[2].set_xlabel('t (s)')
            axs[2].set_ylabel('Z (m)')
            axs[2].set_ylim(0.25, 0.5)
            axs[2].legend()
            axs[2].plot(t, demo_p[:, 2], label='Demonstration')
            plt_dmp_z, = axs[2].plot([], [], label='DMP')
            
            axs[3].set_xlabel('t (s)')
            axs[3].set_ylabel('|| Demo - DMP ||')
            axs[3].set_ylim(0, round(max_error,2))
            plt_error, = axs[3].plot([], [], label='Euclidian diff of Demo and DMP')

            ani = animation.FuncAnimation(fig, animate2D, fargs=[t, plt_dmp_x, plt_dmp_y, plt_dmp_z, plt_error, dmp_p, tbar.update], frames=n_steps-1, interval=25, blit=False, repeat=False)
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=60, bitrate=2000)
            ani.save('2D_ori_param.mp4', writer=writer)
            #plt.show()

    def plot_euclidian_diff(self, demo_p, ts, tau, obs_traj, start_obs_mov):
        n_steps = len(ts)
        # Calculating dmp with and without attractor term
        dmp_p_w_att, _ = self.rollout_moving_obstacle(ts, tau, obs_traj, start_obs_mov, demo_p, acctractor_term=True)
        dmp_p, _ = self.rollout_moving_obstacle(ts, tau, obs_traj, start_obs_mov, demo_p, acctractor_term=False)

        max_without = np.max(np.linalg.norm(demo_p - dmp_p, axis=1))
        avg_without = np.mean(np.linalg.norm(demo_p - dmp_p, axis=1))

        max_with = np.max(np.linalg.norm(demo_p - dmp_p_w_att, axis=1))
        avg_with = np.mean(np.linalg.norm(demo_p - dmp_p_w_att, axis=1))
        print(f"Max error for dmp without attraction {max_without:.4f}")
        print(f"Average error for dmp without attraction {avg_without:.4f}")

        print(f"Max error for dmp with attraction {max_with:.4f}")
        print(f"Average error for dmp with attraction {avg_with:.4f}")

        textstr = '\n'.join((
                            r'$max(|| Demo - DMP ||)$ without attraction$=%.4f$' % (max_without, ),
                            r'$avg(|| Demo - DMP ||)$ without attraction$=%.4f$' % (avg_without, ),
                            r'$max(|| Demo - DMP ||)$ with attraction=$%.4f$' % (max_with, ),
                            r'$avg(|| Demo - DMP ||)$ with attraction=$%.4f$' % (avg_with, ),
                            ))
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)

        fig = plt.figure()
        ax = fig.add_axes([0.1, 0.1, 0.8, 0.7])

        ax.text(0, 1.2, textstr, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)

        t = np.arange(0, tau, 0.002)
        ax.set_xlabel('t (s)')
        ax.set_ylabel('|| Demo - DMP ||')
        ax.plot(t, np.linalg.norm(demo_p - dmp_p, axis=1), label='Error without attraction field')
        ax.plot(t, np.linalg.norm(demo_p - dmp_p_w_att, axis=1), label='Error with attraction field ')

        ax.legend()

        plt.show()
          
    def rollout(self, ts, tau):
        self.reset()

        if np.isscalar(tau):
            tau = np.full_like(ts, tau)

        x = self.cs.rollout(ts, tau)  # Integrate canonical system
        dt = np.gradient(ts) # Differential time vector

        n_steps = len(ts)
        p = np.empty((n_steps, 3))
        dp = np.empty((n_steps, 3))
        ddp = np.empty((n_steps, 3))

        for i in range(n_steps):
            p[i], dp[i], ddp[i] = self.step(x[i], dt[i], tau[i])

        return p, dp, ddp

    def reset(self):
        self.p = self.p0.copy()
        self.dp = np.zeros(3)
        self.ddp = np.zeros(3)

    def train(self, positions, ts, tau):
        p = positions

        # Sanity-check input
        if len(p) != len(ts):
            raise RuntimeError("len(p) != len(ts)")

        # Initial- and goal positions
        self.p0 = p[0]
        self.gp = p[-1]

        # Differential time vector
        dt = np.gradient(ts)[:,np.newaxis]

        # Scaling factor
        self.Dp = np.diag(self.gp - self.p0)
        Dp_inv = np.linalg.inv(self.Dp)

        # Desired velocities and accelerations
        d_p = np.gradient(p, axis=0) / dt
        dd_p = np.gradient(d_p, axis=0) / dt

        # Integrate canonical system
        x = self.cs.rollout(ts, tau)

        # Set up system of equations to solve for weights
        def features(xj):
            psi = np.exp(-self.h * (xj - self.c)**2)
            return xj * psi / psi.sum()

        def forcing(j):
            return Dp_inv.dot(tau**2 * dd_p[j]
                - self.alpha * (self.beta * (self.gp - p[j]) - tau * d_p[j]))

        A = np.stack(features(xj) for xj in x)
        f = np.stack(forcing(j) for j in range(len(ts)))

        # Least squares solution for Aw = f (for each column of f)
        self.w = np.linalg.lstsq(A, f, rcond=None)[0].T

        # Cache variables for later inspection
        self.train_p = p
        self.train_d_p = d_p
        self.train_dd_p = dd_p