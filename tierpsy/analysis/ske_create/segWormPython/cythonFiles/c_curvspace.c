#include <math.h>
#include <stdio.h>
#include <stdlib.h>

double distance(double *x, double *y, int p_dim);
void interpintv(double *pt1, double *pt2, int p_dim, double intv, double *newpt);

inline int ind(m, d, ndim) {
    return m*ndim + d; 
}
double c_curvspace(double *points, int p_size, int p_dim, int N, double *output)
{
    
    /*
    Resamples a curve into N points whose norm is equaly spaced.
    points -> the pointer to the data of p_size x p_dim dimensions.
    p_size -> number of points original data
    p_dim -> number of dimensions
    N -> number of points (resampling) in the output array 
    output -> pointer to the output array
     */
    
//%% initial settings %%
    //input   
    //helper variables
    double totaldist, intv, remainder, distsum, disttmp;
    double dum, R;
    int p_ind_first, kk, k0, k;
    
    double *ptnow = malloc(sizeof (double)*p_dim);
    double *newpt = malloc(sizeof (double)*p_dim);
    double *pttarget = malloc(sizeof (double)*p_dim);
    
    //%% distance between points in p %%
    totaldist = 0;
    for(k0 = 0; k0<p_size-1; k0++)
    {
        R = 0;
        for(k = 0; k<p_dim; k++)
        {
            dum = points[ind(k0,k, p_dim)]-points[ind(k0+1,k, p_dim)];
            R += dum*dum;
        }
        
        totaldist += sqrt(R);
    }
    //%% interval %%
    intv = totaldist/(N-1);
    
    
    for (k = 0; k<p_dim; k++)
    {
        output[k] = points[ind(0,k, p_dim)]; //% copy the first output point
        ptnow[k] = points[ind(0,k, p_dim)]; //initialize the current point
        
    }
    
    //%% iteration %%
    p_ind_first = 1;
    int q_ind;
    for (q_ind = 1; q_ind < N; q_ind++)
    {
        distsum = 0;
        remainder = intv; //% remainder of distance that should be accumulated
        kk = 0;
        
        while(1)
        {
            for(k=0; k<p_dim; k++)
                pttarget[k] = points[ind(p_ind_first+kk,k, p_dim)];
            
            
            //% calculate the distance from active point to the closest point in p
            disttmp = distance(ptnow, pttarget, p_dim);
            
            //add that distance to the total distance from the resampled point
            distsum += disttmp;
            
            //% if distance is enough, generate newpt else, accumulate distance
            if (distsum >= intv)
            {
                interpintv(ptnow, pttarget, p_dim, remainder, newpt);
                break;
            }
            else
            {
                remainder -= disttmp;
                kk++;
                for(k=0; k<p_dim; k++)
                    ptnow[k] = pttarget[k];
                
                if (p_ind_first+kk == p_size)
                {
                    for(k=0; k<p_dim; k++)
                        newpt[k] = points[ind(p_size-1,k, p_dim)];
                    break;
                }
            }
        }
        
        p_ind_first += kk;
        //% add to the new resampled point
        for(k=0; k<p_dim; k++)
        {
            output[ind(q_ind,k, p_dim)] = newpt[k];
            ptnow[k] = newpt[k]; //% update current point
        }
        
   
    }
    //put total distance as function output
    
    return totaldist;
}

double distance(double *x, double *y, int p_dim)
{
//calculate the distance between two points
    double dum;
    double R = 0;
    int k;
    for(k = 0; k<p_dim; k++)
    {
        dum = x[k]-y[k];
        R+= dum*dum;
    }
    R = sqrt(R);
    return R;
}

void interpintv(double *pt1, double *pt2, int p_dim, double intv, double *newpt)
{
    //interpolates a point between points pt1 and pt2 with intv magnitud.
    //results are save into the newpt direction.
    double dum;
    double normR = 0;
    int k;
    
    for(k = 0; k<p_dim; k++)
    {
        dum = pt2[k]-pt1[k];
        normR += dum*dum;
    }
    normR = sqrt(normR);
    
    for(k = 0; k<p_dim; k++)
    {
        newpt[k] = intv*(pt2[k]-pt1[k])/normR + pt1[k];
    }
            
}